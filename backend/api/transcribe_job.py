r"""POST /api/projects/{id}/transcribe: narration to transcript with the engine's script.

    transcribe.py -a <audio files> --out-dir <project>\transcript --model ...

The transcript already there is moved to the trash first, as one entry, so the
script writes into an empty folder and nothing it writes is mixed with an old
file. If the run fails or is cancelled, whatever it left is removed and the old
transcript comes back from the trash. If it succeeds, the old one stays in the
trash and can be restored from there for seven days.
"""

import os
import re

from i2v import speech

from . import files, projects, snapshot, trash
from .httpio import ApiError, invalid

_LANGUAGE = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})?$")


def _number(body, key, kind, low, high):
    value = body.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or (kind is int and int(value) != value) or not low <= value <= high:
        raise invalid("%s must be a number from %s to %s." % (key, low, high), {"field": key})
    return kind(value)


def parse_options(body):
    model = body.get("model") or speech.DEFAULT_MODEL
    if model not in speech.MODEL_SIZES:
        raise invalid("model must be one of %s." % ", ".join(speech.MODEL_SIZES),
                      {"field": "model"})
    language = body.get("language")
    if language is not None and (not isinstance(language, str) or not _LANGUAGE.match(language)):
        raise invalid("language must be a code such as en, or null to detect it.",
                      {"field": "language"})
    options = ["--model", model]
    if language:
        options += ["--language", language.lower()]
    for key, flag, kind in (("maxChars", "--max-chars", int), ("maxSeconds", "--max-seconds", float),
                            ("minSeconds", "--min-seconds", float)):
        value = _number(body, key, kind, 0, 100000)
        if value:
            options += [flag, value]
    if body.get("fresh") is True:
        options.append("--fresh")
    return options


def engine_missing(app):
    lib = speech.lib_dir(app.config.runtime)
    if not os.path.isdir(lib):
        return ApiError(424, "engine_missing",
                        "The speech engine is not installed. Run Setup.bat to install it, "
                        "then try again.", {"what": "speech"})
    return None


def ffmpeg_missing(app):
    if app.media.tools() is None:
        return ApiError(424, "engine_missing",
                        "ffmpeg was not found. Run Setup.bat, which installs a private copy.",
                        {"what": "ffmpeg"})
    return None


def start(app, request):
    project_id = request.params["id"]
    body = request.json()
    projects.load(app, project_id)
    options = parse_options(body)
    problem = engine_missing(app) or ffmpeg_missing(app)
    if problem:
        raise problem

    with app.jobs.begin() as jobs:
        with app.locks.project(project_id):
            stored = projects.load(app, project_id)
            audio = snapshot.audio_paths(app, project_id)
            if not audio:
                blocker = {"code": "no_audio", "message": "Add the narration audio first."}
                raise ApiError(422, "blocked", blocker["message"], {"blockers": [blocker]})
            out_dir = projects.folder(app, project_id, "transcript")
            old = files.transcript_files(out_dir)
            trash_id = trash.remove_files(app, stored, "transcript", old) if old else None
            args = ["-a"] + list(audio) + ["--out-dir", out_dir] + options

            def finish(job, state):
                return _finish(app, project_id, out_dir, trash_id, job, state)

            try:
                job = jobs.launch("transcribe", "transcribe.py", args, project=stored,
                                  finish=finish, keep={"restore": trash_id})
            except ApiError:
                if trash_id:
                    trash.restore(app, trash_id, check_locks=False)
                raise
    return 202, {"job": job.to_dict()}


def _done_line(job):
    for line in reversed(job.tail):
        if line.strip().startswith("done in"):
            return line.strip()
    return None


def _finish(app, project_id, out_dir, trash_id, job, state):
    if state == "done":
        path = snapshot.choose_transcript(out_dir)
        lines = files.line_count(app, path) if path else 0
        job.result = {"lines": lines, "summary": _done_line(job)}
        projects.touch(app, project_id)
        return state
    put_back(app, out_dir, trash_id)
    return state


def put_back(app, out_dir, trash_id):
    """Remove what a failed run left and restore the transcript it replaced."""
    for path in files.transcript_files(out_dir):
        try:
            os.remove(path)
        except OSError:
            pass
    if trash_id:
        try:
            trash.restore(app, trash_id, check_locks=False)
        except ApiError:
            pass


def recover(app, job):
    """After a restart: a transcription that never finished gets its old transcript back.

    Only when the folder has no transcript at all, so a run that did finish
    writing before the server went down is left as it is.
    """
    trash_id = (job.keep or {}).get("restore")
    if not trash_id or not job.project_id or not projects.exists(app, job.project_id):
        return
    out_dir = projects.folder(app, job.project_id, "transcript")
    if snapshot.choose_transcript(out_dir):
        return
    put_back(app, out_dir, trash_id)
