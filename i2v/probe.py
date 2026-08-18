"""ffmpeg and ffprobe helpers: binary discovery, duration probing, encoder choice."""

import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

# Windows: keep the console window from flashing for every short lived probe.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

CACHE_VERSION = 2


class ProbeError(RuntimeError):
    """Raised when ffmpeg or ffprobe is missing or a probe fails."""


def _run(args, timeout=120):
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
    filename = name + ".exe" if os.name == "nt" else name
    local = os.path.join(project_root, "bin", filename)
    if os.path.isfile(local):
        return local
    found = shutil.which(name)
    if not found:
        raise ProbeError(
            "%s was not found. Install ffmpeg and put it on PATH, or drop "
            "%s into the project 'bin' folder." % (name, filename)
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
#
# x264 runs at ultrafast because the content is a sequence of still frames.
# Measured on static 1080p: ultrafast 393 fps against veryfast 202 fps, for a
# file only about 7 percent larger. The slower presets spend their time on
# motion estimation, which buys nothing when consecutive frames are identical.
# -tune stillimage was measured as making no difference at all, so it is not used.
ENCODERS = {
    "qsv": {
        "codec": "h264_qsv",
        "pix_fmt": "nv12",
        "args": ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "24"],
    },
    "x264": {
        "codec": "libx264",
        "pix_fmt": "yuv420p",
        "args": ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20"],
    },
}

# Frames used by the speed trial. Enough to get past encoder startup without
# making first run feel slow.
TRIAL_FRAMES = 600


def _trial(tools, profile):
    """Time an encoder on synthetic still frames. Returns fps, or None if unusable.

    Which encoder is fastest genuinely varies by machine. A weak integrated GPU
    can lose to a strong CPU, and the reverse is just as common, so the answer
    is measured rather than assumed. The result is cached, so this runs once.
    """
    args = [
        tools.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostats",
        "-f", "lavfi", "-i", "color=c=gray:s=1920x1080:r=30",
        "-vf", "format=%s" % profile["pix_fmt"],
        "-frames:v", str(TRIAL_FRAMES), "-fps_mode", "cfr",
        *profile["args"], "-g", "300", "-an", "-f", "null", "-",
    ]
    started = time.time()
    try:
        result = _run(args, timeout=120)
    except subprocess.TimeoutExpired:
        return None
    elapsed = time.time() - started
    if result.returncode != 0 or result.stderr.strip() or elapsed <= 0:
        return None
    return TRIAL_FRAMES / elapsed


def _read_cache(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            cached = json.load(handle)
    except (OSError, ValueError):
        return None
    if cached.get("version") != CACHE_VERSION:
        return None
    if cached.get("name") not in ENCODERS:
        return None
    return cached


def detect_encoder(tools, requested, cache_dir, on_message=None):
    """Return an encoder profile, picking the fastest one this machine has.

    The choice is cached in <cache_dir>/.encoder.json. Delete that file to force
    a fresh trial, or pass an explicit --encoder to skip trials entirely.
    """
    if requested in ENCODERS:
        return dict(ENCODERS[requested], name=requested, fps=None)

    cache_file = os.path.join(cache_dir, ".encoder.json")
    cached = _read_cache(cache_file)
    if cached:
        return dict(ENCODERS[cached["name"]], name=cached["name"], fps=cached.get("fps"))

    if on_message:
        on_message("  first run: timing the available encoders, this is cached afterwards")

    results = {}
    for name, profile in ENCODERS.items():
        speed = _trial(tools, profile)
        if speed:
            results[name] = speed
            if on_message:
                on_message("    %-5s %4.0f fps" % (name, speed))
        elif on_message:
            on_message("    %-5s unavailable" % name)

    if not results:
        raise ProbeError(
            "No usable H.264 encoder was found. Check that this ffmpeg build "
            "includes libx264."
        )

    chosen = max(results, key=results.get)
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as handle:
            json.dump({"version": CACHE_VERSION, "name": chosen,
                       "fps": round(results[chosen]), "trials": {
                           key: round(value) for key, value in results.items()}},
                      handle, indent=2)
    except OSError:
        pass

    return dict(ENCODERS[chosen], name=chosen, fps=results[chosen])
