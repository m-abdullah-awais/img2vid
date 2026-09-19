r"""The narration as the browser's preview plays it: one stream, and its waveform.

    GET /api/projects/{id}/narration                 the narration, one playable file
    GET /api/projects/{id}/narration/peaks?perSecond=50
                                                     {seconds, perSecond, peaks}

The preview is played by the browser from these and the project's images. It
renders nothing, so it can run while a video builds and costs that build nothing.

A single audio file a browser can play is served as it is. Several files, or a
format a browser cannot play such as .wma, are joined into one AAC stream with
the same concat filter the transcription step uses, so the timeline the browser
plays is the timeline the video is built on. The join and the waveform are both
cached in the work folder under a signature of the narration files, so each is
made once per narration.

Making either one runs ffmpeg, so it takes a thumbnail worker slot and is never
started while a render or a transcription runs. Asked for then, and not cached
yet, the answer is 503 not_ready, and the page asks again once the job is done.
"""

import array
import hashlib
import json
import os
import secrets
import subprocess
import sys
import threading

from i2v import paths, probe

from . import projects
from .httpio import ApiError, api_url, content_type, invalid, not_found, send_file, send_json

# What a browser's <audio> element plays without help. Anything else is joined.
BROWSER_PLAYS = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac")

# The waveform is read at 8 kHz mono, plenty for a drawing, and cheap to hold.
PEAK_RATE = 8000
PER_SECOND = (10, 200)
DEFAULT_PER_SECOND = 50

# One join or one waveform at a time is plenty; they are made once per narration.
_MAKING = threading.Lock()


def narration_files(app, project_id):
    """The project's audio files, in the order the video joins them."""
    return paths.listing(projects.folder(app, project_id, "audio"), paths.AUDIO_EXTENSIONS)


def signature(files):
    """Changes whenever the narration does: names, sizes and modification times."""
    digest = hashlib.sha1()
    for path in files:
        info = os.stat(path)
        digest.update(("%s|%d|%d\n" % (os.path.basename(path), info.st_size,
                                       info.st_mtime_ns)).encode("utf-8"))
    return digest.hexdigest()[:16]


def urls(project_id, files):
    """The snapshot's narration URLs, versioned so the browser caches them safely."""
    if not files:
        return None, None
    version = signature(files)
    return (api_url("projects", project_id, "narration", v=version),
            api_url("projects", project_id, "narration", "peaks", v=version))


def plays_as_is(files):
    return len(files) == 1 and files[0].lower().endswith(BROWSER_PLAYS)


def _not_ready(what):
    return ApiError(503, "not_ready",
                    "The %s is made once the running job has finished." % what,
                    {"retryAfter": 5})


def _decode_args(tools, files):
    """ffmpeg arguments that read every file as one continuous track."""
    args = [tools.ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    for path in files:
        args += ["-i", path]
    if len(files) > 1:
        # The filter, not the demuxer, because the files can be any mix of
        # formats and rates. Same reasoning as transcribe.join_audio.
        joined = "".join("[%d:a]" % index for index in range(len(files)))
        args += ["-filter_complex", "%sconcat=n=%d:v=0:a=1[out]" % (joined, len(files)),
                 "-map", "[out]"]
    else:
        args += ["-map", "0:a:0"]
    return args


def _make(app, target, what, run):
    """Run `run(tools, temporary)` once to make `target`, under a thumbnail slot."""
    if os.path.isfile(target):
        return target
    if app.jobs.running() is not None:
        raise _not_ready(what)
    tools = app.media.tools()
    if tools is None:
        raise ApiError(424, "engine_missing", "ffmpeg was not found. Run Setup.bat.",
                       {"what": "ffmpeg"})
    with _MAKING, app.thumbs.slot():
        if os.path.isfile(target):
            return target
        os.makedirs(os.path.dirname(target), exist_ok=True)
        temporary = "%s.%s.tmp%s" % (target, secrets.token_hex(4), os.path.splitext(target)[1])
        try:
            run(tools, temporary)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                try:
                    os.remove(temporary)
                except OSError:
                    pass
    return target


def joined_audio(app, files):
    """The narration as one AAC file in the work folder, made once."""
    target = os.path.join(app.config.work, "preview", signature(files) + ".m4a")

    def run(tools, temporary):
        result = subprocess.run(
            _decode_args(tools, files) + ["-vn", "-c:a", "aac", "-b:a", "128k",
                                          "-movflags", "+faststart", temporary],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=600, creationflags=probe.NO_WINDOW)
        if result.returncode != 0 or not os.path.isfile(temporary):
            raise ApiError(500, "internal", "Could not join the narration for the preview. %s"
                           % result.stderr.decode("utf-8", "replace").strip()[-300:])

    return _make(app, target, "preview of the narration", run)


def compute_peaks(data, per_second):
    """Loudness per slice of raw 16 bit little endian mono at PEAK_RATE, 0 to 255.

    Scaled so the loudest slice is 255. Narration is often recorded quietly, and a
    waveform that fills a fifth of its track says nothing about where the pauses
    are, which is what the timeline needs it for.
    """
    samples = array.array("h")
    samples.frombytes(data[:len(data) - len(data) % 2])
    if sys.byteorder == "big":
        samples.byteswap()
    bucket = max(1, PEAK_RATE // per_second)
    raw = []
    for start in range(0, len(samples), bucket):
        chunk = samples[start:start + bucket]
        raw.append(max(max(chunk), -min(chunk)))
    loudest = max(raw) if raw else 0
    if loudest <= 0:
        return [0] * len(raw), len(samples) / PEAK_RATE
    return [min(255, value * 255 // loudest) for value in raw], len(samples) / PEAK_RATE


def peaks(app, files, per_second):
    """{seconds, perSecond, peaks}, cached as JSON in the work folder."""
    target = os.path.join(app.config.work, "peaks",
                          "%s-%d.json" % (signature(files), per_second))

    def run(tools, temporary):
        result = subprocess.run(
            _decode_args(tools, files) + ["-vn", "-ac", "1", "-ar", str(PEAK_RATE),
                                          "-f", "s16le", "-"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=600, creationflags=probe.NO_WINDOW)
        if result.returncode != 0:
            raise ApiError(500, "internal", "Could not read the narration's waveform. %s"
                           % result.stderr.decode("utf-8", "replace").strip()[-300:])
        values, seconds = compute_peaks(result.stdout, per_second)
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump({"seconds": round(seconds, 3), "perSecond": per_second,
                       "peaks": values}, handle, separators=(",", ":"))

    path = _make(app, target, "waveform", run)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

def _files_or_404(app, project_id):
    projects.load(app, project_id)
    files = narration_files(app, project_id)
    if not files:
        raise not_found("This project has no narration yet.")
    return files


def _cache(request, files):
    """Immutable when the URL names the narration it expects, else revalidate."""
    wanted = request.query.get("v")
    return ("private, max-age=31536000, immutable" if wanted and wanted == signature(files)
            else "no-cache")


def narration_route(app, request):
    """GET or HEAD /api/projects/{id}/narration, with Range."""
    files = _files_or_404(app, request.params["id"])
    cache = _cache(request, files)
    head = request.method == "HEAD"
    if plays_as_is(files):
        send_file(request.handler, files[0], content_type(files[0]), head=head, cache=cache)
    else:
        send_file(request.handler, joined_audio(app, files), "audio/mp4", head=head,
                  cache=cache)
    return None


def peaks_route(app, request):
    """GET /api/projects/{id}/narration/peaks?perSecond=50"""
    files = _files_or_404(app, request.params["id"])
    try:
        per_second = int(request.query.get("perSecond") or DEFAULT_PER_SECOND)
    except ValueError:
        raise invalid("perSecond must be a number from %d to %d." % PER_SECOND)
    if not PER_SECOND[0] <= per_second <= PER_SECOND[1]:
        raise invalid("perSecond must be a number from %d to %d." % PER_SECOND)
    payload = peaks(app, files, per_second)
    send_json(request.handler, 200, payload,
              headers=[("Cache-Control", _cache(request, files))],
              head=request.method == "HEAD")
    return None
