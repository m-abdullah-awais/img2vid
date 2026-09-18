"""Who may touch which files, and when.

Three kinds of lock live here.

Job locks. A running render reads the project's images, audio and transcript
from disk while it encodes, so none of them may change underneath it. A
transcription reads the audio and rewrites the transcript. A mutation that
touches a locked part gets 423 `locked`.

Project locks. One re-entrant lock per project serialises the mutations
themselves, so two uploads racing for one name, or an arrange landing in the
middle of an upload, cannot interleave.

The images read/write lock. Windows refuses to rename a file while any other
handle has it open, and neither Python nor ffmpeg opens files with delete
sharing. A rename landing while a thumbnail is being made, or while the file is
being served, would fail half way through a two pass renumber. Reading an image
takes the shared side, renaming takes the exclusive side.
"""

import contextlib
import threading
import time

from .httpio import ApiError

PARTS = ("audio", "transcript", "images")

# What each kind of job holds for its project while it runs.
JOB_LOCKS = {
    "render": ("audio", "images", "transcript"),
    "transcribe": ("audio", "transcript"),
}

WHAT = {
    "render": "a video is being built for %s",
    "transcribe": "%s is being transcribed",
}


class ReadWrite:
    """Many readers or one writer, with writers served first.

    A writer that has waited `patience` seconds goes ahead anyway rather than
    stall behind a slow client. The rename code rolls back if Windows then
    refuses a move, so the worst case is a refused request, never a half
    renamed folder.
    """

    def __init__(self):
        self._cond = threading.Condition()
        self._readers = 0
        self._writer = False
        self._waiting = 0

    @contextlib.contextmanager
    def shared(self):
        with self._cond:
            while self._writer or self._waiting:
                self._cond.wait()
            self._readers += 1
        try:
            yield
        finally:
            with self._cond:
                self._readers -= 1
                self._cond.notify_all()

    @contextlib.contextmanager
    def exclusive(self, patience=15.0):
        deadline = time.monotonic() + patience
        with self._cond:
            self._waiting += 1
            try:
                while self._readers and time.monotonic() < deadline:
                    self._cond.wait(max(0.01, deadline - time.monotonic()))
                while self._writer:
                    self._cond.wait()
                self._writer = True
            finally:
                self._waiting -= 1
        try:
            yield
        finally:
            with self._cond:
                self._writer = False
                self._cond.notify_all()


class Locks:
    def __init__(self, app):
        self.app = app
        self._guard = threading.Lock()
        self._projects = {}
        self._images = {}

    def project(self, project_id):
        with self._guard:
            lock = self._projects.get(project_id)
            if lock is None:
                lock = self._projects[project_id] = threading.RLock()
            return lock

    def images(self, project_id):
        with self._guard:
            lock = self._images.get(project_id)
            if lock is None:
                lock = self._images[project_id] = ReadWrite()
            return lock

    def holder(self, project_id):
        """The running job that holds this project's files, if any."""
        job = self.app.jobs.running()
        if job is None or job.project_id != project_id or job.kind not in JOB_LOCKS:
            return None
        return job

    def state(self, project_id):
        job = self.holder(project_id)
        held = JOB_LOCKS.get(job.kind, ()) if job else ()
        return {part: part in held for part in PARTS}

    def check(self, project_id, *parts):
        """Refuse with 423 when a running job holds any of these parts."""
        job = self.holder(project_id)
        if job is None:
            return
        held = [part for part in parts if part in JOB_LOCKS[job.kind]]
        if not held:
            return
        doing = WHAT[job.kind] % (job.project_name or "this project")
        raise ApiError(423, "locked",
                       "The %s cannot change while %s. Wait for it to finish or cancel it."
                       % (_joined(held), doing),
                       {"job": job.to_dict()})


def _joined(parts):
    words = {"audio": "narration", "transcript": "transcript", "images": "images"}
    names = [words[part] for part in parts]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]
