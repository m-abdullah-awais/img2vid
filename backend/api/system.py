r"""GET /api/system and the two system jobs: the self-test and a model download.

Everything reported here comes from looking at files, never from loading
anything. The server must not import faster_whisper or ctranslate2, which are
large and belong to the transcription child process alone, and it must not
time the encoders, which is a minute of full CPU. The encoder shown is the one
the engine cached after its own trial, when it has run one.
"""

import os
import platform
import shutil
import subprocess
import sys
import threading

from i2v import probe, speech

from . import projects, trash, transcribe_job
from .httpio import invalid

MODEL_NOTES = {
    "tiny": "Fastest, but about twice the mistakes of base. Rarely worth it.",
    "base": "Recommended. About six times faster than real time on a laptop CPU.",
    "small": "About seven times slower than base, and no more accurate on narration.",
}

_node = {}
_node_lock = threading.Lock()


def _inside(path, folder):
    try:
        return os.path.commonpath([os.path.normcase(os.path.abspath(path)),
                                   os.path.normcase(os.path.abspath(folder))]) \
            == os.path.normcase(os.path.abspath(folder))
    except ValueError:
        return False


def _version_of(executable):
    try:
        result = subprocess.run([executable, "--version"], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=10,
                                creationflags=probe.NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


def node_info(app):
    """Node's version and path, found once: the private copy first, then PATH."""
    with _node_lock:
        if "value" in _node:
            return _node["value"]
        candidates = []
        if os.path.isfile(app.config.node):
            candidates.append(app.config.node)
        found = shutil.which("node")
        if found:
            candidates.append(found)
        value = {"version": None, "path": None}
        for candidate in candidates:
            version = _version_of(candidate)
            if version:
                value = {"version": version, "path": candidate}
                break
        _node["value"] = value
        return value


def ffmpeg_info(app):
    local = os.path.join(app.config.bin, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if os.path.isfile(local):
        return {"found": True, "path": local, "source": "runtime"}
    found = shutil.which("ffmpeg")
    if found:
        return {"found": True, "path": found, "source": "path"}
    return {"found": False, "path": None, "source": None}


def speech_info(app):
    runtime = app.config.runtime
    lib = speech.lib_dir(runtime)
    installed = os.path.isdir(lib)
    built_for = None
    marker = os.path.join(lib, speech.VERSION_MARKER)
    if os.path.isfile(marker):
        try:
            with open(marker, "r", encoding="utf-8", errors="replace") as handle:
                built_for = handle.read().strip() or None
        except OSError:
            pass
    return {
        "installed": installed,
        "builtFor": built_for,
        "matches": installed and (built_for is None or built_for == speech.python_tag()),
        "models": [{"name": name, "local": speech.model_is_local(runtime, name),
                    "note": MODEL_NOTES.get(name, "")} for name in speech.MODEL_SIZES],
        "default": speech.DEFAULT_MODEL,
    }


def _folder_size(folder):
    total = 0
    for where, _, names in os.walk(folder):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(where, name))
            except OSError:
                pass
    return total


def info(app):
    encoder = probe._read_cache(os.path.join(app.config.engine_work, ".encoder.json"))
    return {
        "python": {"version": platform.python_version(), "path": sys.executable,
                   "source": "runtime" if _inside(sys.executable, app.config.runtime) else "path"},
        "ffmpeg": ffmpeg_info(app),
        "node": node_info(app),
        "encoder": {"name": encoder["name"], "fps": encoder.get("fps")} if encoder else None,
        "speech": speech_info(app),
        "storage": {"bytes": _folder_size(app.config.storage),
                    "projects": len(projects.ids(app)),
                    "trashBytes": trash.size(app)},
        "guard": bool(app.guard),
    }


def info_route(app, request):
    return 200, info(app)


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------

def _check_finished(job, state):
    passed = [line.strip() for line in job.tail if line.strip().startswith("[x]")]
    failed = [line.strip() for line in job.tail if line.strip().startswith("[!]")]
    if failed:
        job.error = "\n".join(failed)
        job.result = {"summary": "%d of %d checks failed" % (len(failed), len(passed) + len(failed))}
    elif state == "done":
        job.result = {"summary": "All %d checks passed" % len(passed)}
    return state


def check(app, request):
    request.json()
    with app.jobs.begin() as jobs:
        job = jobs.launch("check", "setup_check.py", [], finish=_check_finished)
    return 202, {"job": job.to_dict()}


def model(app, request):
    wanted = request.json().get("model")
    if wanted not in speech.MODEL_SIZES:
        raise invalid("model must be one of %s." % ", ".join(speech.MODEL_SIZES),
                      {"field": "model"})
    problem = transcribe_job.engine_missing(app)
    if problem:
        raise problem

    def finished(job, state):
        if state == "done":
            job.result = {"summary": "The %s model is ready." % wanted}
        return state

    with app.jobs.begin() as jobs:
        job = jobs.launch("model", "setup_speech.py", [wanted], finish=finished)
    return 202, {"job": job.to_dict()}
