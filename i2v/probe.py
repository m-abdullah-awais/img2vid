"""ffmpeg and ffprobe helpers: binary discovery, duration probing, encoder choice."""

import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

# Windows: keep the console window from flashing for every short lived probe.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ProbeError(RuntimeError):
    """Raised when ffmpeg or ffprobe is missing or a probe fails."""


def _run(args, timeout=60):
    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=NO_WINDOW,
    )


def _locate(name, project_root):
    """Prefer a project local binary, then fall back to PATH."""
    local = os.path.join(project_root, "bin", name + ".exe" if os.name == "nt" else name)
    if os.path.isfile(local):
        return local
    found = shutil.which(name)
    if not found:
        raise ProbeError(
            "%s was not found. Install ffmpeg and put it on PATH, or drop "
            "%s into the project 'bin' folder." % (name, name)
        )
    return found


class Tools:
    """Resolved paths to the ffmpeg and ffprobe binaries."""

    def __init__(self, project_root):
        self.root = project_root
        self.ffmpeg = _locate("ffmpeg", project_root)
        self.ffprobe = _locate("ffprobe", project_root)


def duration(tools, path):
    """Return the duration of a media file in seconds."""
    result = _run([
        tools.ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ])
    value = result.stdout.strip()
    if result.returncode != 0 or not value or value == "N/A":
        raise ProbeError("Could not read the duration of %s. %s" % (path, result.stderr.strip()))
    return float(value)


def total_duration(tools, paths):
    """Sum the durations of several files. Probes run concurrently."""
    if len(paths) == 1:
        return duration(tools, paths[0])
    with ThreadPoolExecutor(max_workers=min(8, len(paths))) as pool:
        return float(sum(pool.map(lambda item: duration(tools, item), paths)))


# Encoder profiles. Each entry lists the ffmpeg arguments and the pixel format
# the filter chain should hand over.
ENCODERS = {
    "qsv": {
        "codec": "h264_qsv",
        "pix_fmt": "nv12",
        "args": ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "24"],
    },
    "x264": {
        "codec": "libx264",
        "pix_fmt": "yuv420p",
        "args": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-tune", "stillimage"],
    },
}

_PREFERENCE = ["qsv", "x264"]


def _works(tools, codec):
    """Encode a fraction of a second of black to see if the encoder initialises."""
    result = _run([
        tools.ffmpeg, "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=black:s=640x360:r=30:d=0.2",
        "-c:v", codec, "-f", "null", "-",
    ], timeout=45)
    return result.returncode == 0 and not result.stderr.strip()


def detect_encoder(tools, requested, cache_dir):
    """Return an encoder profile. The auto-detection result is cached on disk.

    Probing a hardware encoder costs a process launch, so the answer is written
    to <cache_dir>/.encoder.json and reused on later runs.
    """
    if requested in ENCODERS:
        return dict(ENCODERS[requested], name=requested)

    cache_file = os.path.join(cache_dir, ".encoder.json")
    try:
        with open(cache_file, "r", encoding="utf-8") as handle:
            cached = json.load(handle).get("name")
        if cached in ENCODERS:
            return dict(ENCODERS[cached], name=cached)
    except (OSError, ValueError):
        pass

    chosen = "x264"
    for name in _PREFERENCE:
        if _works(tools, ENCODERS[name]["codec"]):
            chosen = name
            break

    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as handle:
            json.dump({"name": chosen}, handle)
    except OSError:
        pass

    return dict(ENCODERS[chosen], name=chosen)
