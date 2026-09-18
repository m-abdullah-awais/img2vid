r"""One job at a time: a script run as a child process, its log and its history.

Every job is one of the scripts in backend\cli\, run exactly as a person would
run it from a terminal:

    sys.executable -u backend\cli\<script> ...

with no console window, stdin closed, and stderr folded into stdout. One reader
thread per job drains that pipe continuously. Speed is this project's first
priority, and a pipe nobody reads fills up and stalls the render.

Only one job runs at a time across every project, because each one saturates
the CPU on its own. Finished jobs are kept in work\api\jobs.json, and a job
found still marked running when the server starts is recorded as interrupted.
"""

import collections
import contextlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback

from i2v import paths, probe

from . import processes
from .httpio import ApiError, iso, parse_iso
from .parse_output import OutputParser

RING = 2000
HISTORY = 20
KEEP_IN_MEMORY = 60

FIRST_PHASE = {"render": "Starting", "transcribe": "Starting", "check": "Checking",
               "model": "Downloading model"}

BUSY = {
    "render": "A video is being built for %s. Wait for it or cancel it.",
    "transcribe": "%s is being transcribed. Wait for it or cancel it.",
    "check": "The system check is running. Wait for it or cancel it.",
    "model": "A speech model is being downloaded. Wait for it or cancel it.",
}

_ARGPARSE_ERROR = re.compile(r"^\S+: error: (.*)$")


class Job:
    def __init__(self, kind, project_id=None, project_name=None, phase="Starting"):
        self.id = "%s-%s" % (time.strftime("%Y%m%d-%H%M%S"), secrets.token_hex(2))
        self.kind = kind
        self.project_id = project_id
        self.project_name = project_name
        self.state = "running"
        self.phase = phase
        self.progress = None
        self.started = time.time()
        self.ended = None
        self.exit_code = None
        self.error = None
        self.result = None
        self.process = None
        self.cancelled = False
        self.children = []
        self.done = threading.Event()
        self.tail = collections.deque(maxlen=400)
        self.finish = None
        self.keep = {}
        self.elapsed_at_load = None

    def elapsed(self):
        if self.elapsed_at_load is not None and self.state != "running":
            return self.elapsed_at_load
        return max(0.0, (self.ended or time.time()) - self.started)

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "projectId": self.project_id,
            "projectName": self.project_name,
            "state": self.state,
            "phase": self.phase,
            "progress": None if self.progress is None else round(self.progress, 4),
            "startedAt": iso(self.started),
            "endedAt": iso(self.ended) if self.ended else None,
            "elapsed": round(self.elapsed(), 1),
            "exitCode": self.exit_code,
            "error": self.error,
            "result": self.result,
        }

    def record(self):
        data = self.to_dict()
        data["keep"] = self.keep
        return data

    @classmethod
    def from_record(cls, data):
        job = cls(data.get("kind") or "render", data.get("projectId"), data.get("projectName"))
        job.id = data.get("id") or job.id
        job.state = data.get("state") or "interrupted"
        job.phase = data.get("phase") or "Finished"
        job.progress = data.get("progress")
        job.started = parse_iso(data.get("startedAt")) or time.time()
        job.ended = parse_iso(data.get("endedAt"))
        job.exit_code = data.get("exitCode")
        job.error = data.get("error")
        job.result = data.get("result")
        job.keep = data.get("keep") or {}
        job.elapsed_at_load = data.get("elapsed")
        job.done.set()
        return job


def busy(job):
    return ApiError(409, "busy", BUSY.get(job.kind, "A job is running. Wait for it or cancel it.")
                    % (job.project_name or "this project"), {"job": job.to_dict()})


class JobManager:
    def __init__(self, app):
        self.app = app
        self._start = threading.RLock()
        self._lock = threading.Lock()
        self._save = threading.Lock()
        self._current = None
        self._history = []
        self._ring = collections.deque(maxlen=RING)
        self._seq = 0
        self._dropped = 0

    # ---------------------------------------------------------------- state

    def running(self):
        with self._lock:
            job = self._current
        return job if job is not None and job.state == "running" else None

    def latest(self):
        with self._lock:
            if self._current is not None:
                return self._current
            return self._history[-1] if self._history else None

    def latest_for(self, project_id):
        with self._lock:
            for job in reversed(self._history):
                if job.project_id == project_id:
                    return job
        return None

    def recent(self, count=HISTORY):
        with self._lock:
            return list(reversed(self._history[-count:]))

    def events(self, since):
        with self._lock:
            last = self._seq
            if since is None or since < 0 or since > last:
                since = 0
            items = [{"seq": seq, "text": text} for seq, text in self._ring if seq > since]
            return items, last, since < self._dropped

    # ---------------------------------------------------------------- history

    def load(self):
        """Read the history. Returns the jobs that were running when the server stopped."""
        try:
            with open(self.app.config.jobs_file, "r", encoding="utf-8") as handle:
                records = json.load(handle).get("jobs", [])
        except (OSError, ValueError, AttributeError):
            records = []
        interrupted = []
        with self._lock:
            for record in records:
                if not isinstance(record, dict):
                    continue
                job = Job.from_record(record)
                if job.state == "running":
                    job.state = "interrupted"
                    job.phase = "Finished"
                    job.ended = time.time()
                    job.elapsed_at_load = record.get("elapsed") or 0.0
                    interrupted.append(job)
                self._history.append(job)
        self._persist()
        return interrupted

    def _persist(self):
        with self._lock:
            records = [job.record() for job in self._history[-HISTORY:]]
        path = self.app.config.jobs_file
        with self._save:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                temporary = "%s.%s.tmp" % (path, secrets.token_hex(3))
                with open(temporary, "w", encoding="utf-8") as handle:
                    json.dump({"jobs": records}, handle, indent=2, ensure_ascii=False)
                os.replace(temporary, path)
            except OSError:
                pass

    # ---------------------------------------------------------------- running

    @contextlib.contextmanager
    def begin(self):
        """Hold the right to start a job. Refuses with 409 busy while one runs.

        The caller checks its inputs and calls launch() inside this block, so
        no second job can slip in between the check and the start.
        """
        with self._start:
            job = self.running()
            if job is not None:
                raise busy(job)
            yield self

    def launch(self, kind, script, args, project=None, finish=None, keep=None):
        job = Job(kind, project["id"] if project else None,
                  project["name"] if project else None, FIRST_PHASE.get(kind, "Starting"))
        job.finish = finish
        job.keep = keep or {}
        command = [sys.executable, "-u", self.app.config.script(script)] + [str(a) for a in args]
        # UTF-8 so a file name in any script prints instead of crashing the child
        # on a code page that cannot encode it.
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        try:
            job.process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, creationflags=probe.NO_WINDOW, env=env,
                cwd=paths.ROOT)
        except OSError as error:
            raise ApiError(500, "internal", "Could not start %s: %s" % (script, error))
        with self._lock:
            self._current = job
            self._history.append(job)
            del self._history[:-KEEP_IN_MEMORY]
            self._ring.clear()
            self._dropped = 0
        self._persist()
        threading.Thread(target=self._pump, args=(job,), name="job-" + job.id,
                         daemon=True).start()
        return job

    def _progress(self, job, fraction):
        job.progress = max(0.0, min(1.0, fraction))

    def _phase(self, job, phase):
        job.phase = phase

    def _line(self, job, line):
        with self._lock:
            self._seq += 1
            if len(self._ring) == RING:
                self._dropped = self._ring[0][0]
            self._ring.append((self._seq, line))
        job.tail.append(line)

    def _pump(self, job):
        parser = OutputParser(lambda value: self._progress(job, value),
                              lambda line: self._line(job, line),
                              lambda phase: self._phase(job, phase))
        stream = job.process.stdout
        try:
            while True:
                data = stream.read1(65536)
                if not data:
                    break
                parser.feed(data)
        except (OSError, ValueError):
            pass
        try:
            parser.close()
        except Exception:  # noqa: BLE001 - the log is not worth losing the job over
            pass
        code = job.process.wait()
        try:
            stream.close()
        except OSError:
            pass
        self._sweep(job)
        # A killed child never reaches its own cleanup, so its job_<pid> folder
        # of part files stays behind. This one is known to be dead, and the
        # engine's own sweep takes any older ones. That sweep alone would miss
        # this folder: Popen still holds the child's handle, so it looks alive.
        shutil.rmtree(os.path.join(self.app.config.engine_work, "job_%d" % job.process.pid),
                      ignore_errors=True)
        probe.sweep_stale_jobs(self.app.config.engine_work)

        if job.cancelled:
            state = "cancelled"
        elif code == 0:
            state = "done"
        elif code == 2 and not parser.error and not self._usage_error(job):
            state = "nothing"
        else:
            state = "failed"
        job.exit_code = code
        if state == "failed":
            job.error = parser.error or self._usage_error(job) or self._fallback_error(job, code)

        if job.finish:
            try:
                state = job.finish(job, state) or state
            except Exception as error:  # noqa: BLE001
                traceback.print_exc()
                state = "failed"
                job.error = job.error or "Finishing the job failed: %s" % error
        with self._lock:
            if state == "done" and job.progress is not None:
                job.progress = 1.0
            job.state = state
            job.phase = "Finished"
            job.ended = time.time()
            if self._current is job:
                self._current = None
        self._persist()
        job.done.set()

    def _usage_error(self, job):
        for line in reversed(job.tail):
            match = _ARGPARSE_ERROR.match(line.strip())
            if match:
                return match.group(1)
        return None

    def _fallback_error(self, job, code):
        lines = [line.strip() for line in job.tail if line.strip()]
        if lines:
            return "\n".join(lines[-4:])
        return "It stopped with exit code %s." % code

    def _sweep(self, job):
        """Stop anything the child left running. The job object should already have."""
        survivors = {pid for pid, _ in job.children}
        try:
            survivors.update(pid for pid, _ in processes.descendants(job.process.pid))
        except OSError:
            pass
        deadline = time.monotonic() + 3.0
        while survivors and time.monotonic() < deadline:
            survivors = {pid for pid in survivors if processes.alive(pid)}
            for pid in survivors:
                processes.kill(pid)
            if survivors:
                time.sleep(0.05)

    def cancel(self, wait=10.0):
        """Kill the running job and wait for it to be recorded as cancelled."""
        job = self.running()
        if job is None:
            return self.latest()
        job.cancelled = True
        try:
            job.children = processes.descendants(job.process.pid)
        except OSError:
            job.children = []
        try:
            job.process.kill()
        except OSError:
            pass
        job.done.wait(wait)
        return job

    def stop(self):
        if self.running():
            self.cancel(wait=10.0)
