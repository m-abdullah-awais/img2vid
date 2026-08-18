"""Timeline construction and ffmpeg rendering.

Design note on why the video is built from chunks rather than from a single
concat demuxer pass.

The obvious approach is an ffconcat list of images with a duration per image.
It was measured and rejected. The concat demuxer stores durations in whole
microseconds, and a 30fps frame boundary is 33333.33 microseconds, so it is not
representable. Cumulative rounding then moves segment boundaries by a frame in
either direction, the final entry ignores its declared duration outright, and
the whole stream is shifted one frame early.

What is used instead is exact by construction. Each image is decoded once,
scaled once, then repeated by the loop filter for an exact frame count, and the
images in a chunk are joined with the concat filter. The output frame count is
pinned with -frames:v, so a segment cannot drift. Chunks encode concurrently to
MPEG-TS and are joined with a stream copy, which re-encodes nothing.

This also happens to be the scalable arrangement: chunk count is what spreads
the work over cores.
"""

import os
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

from .probe import NO_WINDOW

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")

# Images per ffmpeg process. Each image in a chunk costs one decoder and one
# filter chain, so very large chunks slow the graph down. Small chunks pay
# process startup instead. This sits in the flat part of the curve.
CHUNK_SIZE = 24

# How many chunks to aim for per worker. More than one so the pool can even out
# uneven chunks instead of stalling on the last one.
CHUNKS_PER_JOB = 2

_NUM_SPLIT = re.compile(r"(\d+)")
_PROGRESS_RE = re.compile(r"^out_time_(?:us|ms)=(-?\d+)$")
_FRAME_RE = re.compile(r"^frame=\s*(\d+)$")

# Pinned so that every chunk converts colour identically, whatever the source
# image format was. Without this the parts cannot be safely stream copied together.
COLOUR_CONVERSION = "scale=out_color_matrix=bt709:out_range=tv"
COLOUR_TAGS = [
    "-color_range", "tv", "-colorspace", "bt709",
    "-color_primaries", "bt709", "-color_trc", "bt709",
]

_QUOTE = "'"
_ESCAPED_QUOTE = "'\\''"


class RenderError(RuntimeError):
    """Raised when inputs do not line up or ffmpeg fails."""


# Every ffmpeg currently running, so an interrupt can stop them at once instead
# of waiting for the chunk in flight to finish.
_ACTIVE = set()
_ACTIVE_LOCK = threading.Lock()

# Set once the run is being abandoned. Killing the encoders that are already
# running is not enough on its own: the thread pool would simply start the next
# queued chunk, so a cancel could take as long as the remaining work. Chunks
# check this before they launch anything.
_CANCELLED = threading.Event()


def terminate_active():
    """Cancel the run and kill every running ffmpeg. Safe to call repeatedly."""
    _CANCELLED.set()
    with _ACTIVE_LOCK:
        running = list(_ACTIVE)
    for process in running:
        try:
            process.kill()
        except OSError:
            pass
    return len(running)


def cancelled():
    return _CANCELLED.is_set()


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------

def natural_key(name):
    """Sort key that orders 2.png before 10.png instead of after it."""
    parts = _NUM_SPLIT.split(name.lower())
    return [int(part) if part.isdigit() else part for part in parts]


def find_images(folder):
    """Return absolute image paths from a folder, in natural filename order."""
    if not os.path.isdir(folder):
        raise RenderError("Images folder not found: %s" % folder)
    names = [
        name for name in os.listdir(folder)
        if name.lower().endswith(IMAGE_EXTENSIONS)
        and os.path.isfile(os.path.join(folder, name))
    ]
    if not names:
        raise RenderError(
            "No images in %s. Supported extensions: %s"
            % (folder, ", ".join(IMAGE_EXTENSIONS))
        )
    names.sort(key=natural_key)
    return [os.path.abspath(os.path.join(folder, name)) for name in names]


# --------------------------------------------------------------------------
# Timeline
# --------------------------------------------------------------------------

def build_timeline(starts, images, total_audio, fps, force=False, on_warning=None):
    """Pair each image with an exact whole number of frames.

    Every boundary is rounded to a frame once and shared by the segments on
    both sides of it, so rounding error cannot accumulate and the frame counts
    add up to exactly round(total_audio * fps).

    The first image is pulled back to time zero even if the transcript starts
    later, so the video never opens on black.

    Three things can make the inputs unusable: the counts not matching, audio
    that stops before the last timestamp, and two timestamps closer together
    than a single frame. Normally each is a hard error, because silently
    guessing would produce a mistimed video that looks fine until you watch it.
    With force set, each is repaired instead and reported through on_warning.
    """
    warn = on_warning or (lambda text: None)

    # 1. One image per timestamp.
    if len(images) != len(starts):
        if not force:
            raise RenderError(
                "Count mismatch: %d transcript timestamps but %d images.\n"
                "  first images: %s\n"
                "There must be exactly one image per timestamp.\n"
                "Pass --force to build the video anyway from whichever there are fewer of."
                % (
                    len(starts),
                    len(images),
                    ", ".join(os.path.basename(item) for item in images[:5]) or "none",
                )
            )
        keep = min(len(images), len(starts))
        if not keep:
            raise RenderError("Nothing to render: no images or no timestamps.")
        if len(images) > keep:
            warn("--force: %d timestamps but %d images. Ignoring the last %d image(s): %s"
                 % (len(starts), len(images), len(images) - keep,
                    ", ".join(os.path.basename(item) for item in images[keep:][:5])))
        else:
            warn("--force: %d timestamps but %d images. Using the first %d timestamps, "
                 "so image %d holds until the audio ends."
                 % (len(starts), len(images), keep, keep))
        starts, images = starts[:keep], images[:keep]

    # 2. The audio has to outlast the final timestamp, since the last image is
    #    held until the audio ends.
    if total_audio <= starts[-1]:
        if not force:
            raise RenderError(
                "The audio is %.3fs long but the last transcript timestamp is at "
                "%.3fs. The audio must run past the final timestamp.\n"
                "Pass --force to drop the timestamps that fall past the end of the audio."
                % (total_audio, starts[-1])
            )
        keep = sum(1 for value in starts if value < total_audio)
        if not keep:
            raise RenderError(
                "Even with --force there is nothing to render: the audio is %.3fs "
                "long and the first timestamp is at %.3fs."
                % (total_audio, starts[0])
            )
        warn("--force: audio ends at %.3fs. Dropping %d timestamp(s) past that point."
             % (total_audio, len(starts) - keep))
        starts, images = starts[:keep], images[:keep]

    # 3. Quantise to whole frames. The first boundary is pinned to zero so the
    #    video never opens on black.
    end_boundary = round(total_audio * fps)
    pairs = []
    dropped = 0
    for index, (start, image) in enumerate(zip(starts, images)):
        boundary = 0 if index == 0 else round(start * fps)
        if pairs and boundary <= pairs[-1][0]:
            if not force:
                raise RenderError(
                    "Timestamps %d and %d are less than one frame apart at %d fps "
                    "(%.3fs and %.3fs). Increase --fps or merge the lines.\n"
                    "Pass --force to drop the shorter of the two."
                    % (index, index + 1, fps, starts[index - 1], start)
                )
            dropped += 1
            continue
        pairs.append((boundary, image))

    if end_boundary <= pairs[-1][0]:
        # The final image would get no frames at all.
        if not force or len(pairs) == 1:
            raise RenderError(
                "The last timestamp at %.3fs leaves no room before the audio ends "
                "at %.3fs." % (pairs[-1][0] / fps, total_audio)
            )
        dropped += 1
        pairs.pop()

    if dropped:
        warn("--force: dropped %d line(s) shorter than one frame at %d fps." % (dropped, fps))

    timeline = []
    for index, (boundary, image) in enumerate(pairs):
        following = pairs[index + 1][0] if index + 1 < len(pairs) else end_boundary
        timeline.append({
            "index": index,
            "image": image,
            "frames": following - boundary,
            "start": boundary / fps,
            "end": following / fps,
            "seconds": (following - boundary) / fps,
        })
    return timeline


def chunk_timeline(timeline, jobs, chunk_size=CHUNK_SIZE):
    """Split the timeline into contiguous chunks, one ffmpeg process each.

    Chunks are capped at chunk_size images so the filter graph stays small.
    Aiming for CHUNKS_PER_JOB chunks per worker rather than exactly one keeps
    the tail short: with one chunk each, a single slow chunk leaves every other
    core idle until it finishes, and it also means the progress bar only moves
    once per worker.
    """
    jobs = max(1, jobs)
    target = max(1, -(-len(timeline) // (jobs * CHUNKS_PER_JOB)))
    size = min(chunk_size, target)
    return [timeline[start:start + size] for start in range(0, len(timeline), size)]


# --------------------------------------------------------------------------
# Concat lists
# --------------------------------------------------------------------------

def _concat_path(path):
    """Quote a path for the ffconcat file directive."""
    normalised = os.path.abspath(path).replace("\\", "/")
    return normalised.replace(_QUOTE, _ESCAPED_QUOTE)


def write_concat_list(path, items):
    """Write a plain ffconcat list of files, with no duration directives."""
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("ffconcat version 1.0\n")
        for item in items:
            handle.write("file '%s'\n" % _concat_path(item))
    return path


# --------------------------------------------------------------------------
# Filter chain
# --------------------------------------------------------------------------

def geometry_filter(width, height, fit, background):
    """Fit one image to the output frame. This runs once per image."""
    if fit == "cover":
        return ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d"
                % (width, height, width, height))
    return ("scale=%d:%d:force_original_aspect_ratio=decrease,"
            "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=%s"
            % (width, height, width, height, background))


def chunk_filtergraph(entries, options, pix_fmt):
    """Build the filter graph for one chunk.

    Per image: force a common input format, scale and pad once, convert to the
    output colour space once, then hold the single decoded frame for an exact
    number of frames with the loop filter. setpts renumbers the repeats, which
    the loop filter does not do on its own. The concat filter joins the
    segments in order.

    Pinning the input to rgb24 and the output to limited range bt709 matters
    more than it looks. Without it a JPEG decodes as full range yuvj420p and a
    PNG as limited range yuv420p, so chunks built from different source formats
    end up with different colour ranges. Stream copying those together produces
    a visible brightness jump partway through the video.
    """
    geometry = geometry_filter(
        options["width"], options["height"], options["fit"], options["background"]
    )
    chains, labels = [], []
    for position, entry in enumerate(entries):
        chains.append(
            "[%d:v]format=rgb24,%s,setsar=1,%s,format=%s,"
            "loop=loop=%d:size=1:start=0,setpts=N/FR/TB[v%d]"
            % (position, geometry, COLOUR_CONVERSION, pix_fmt,
               entry["frames"] - 1, position)
        )
        labels.append("[v%d]" % position)
    chains.append("%sconcat=n=%d:v=1:a=0[v]" % ("".join(labels), len(entries)))
    return ";".join(chains)


# --------------------------------------------------------------------------
# ffmpeg execution
# --------------------------------------------------------------------------

def _run_ffmpeg(args, total_seconds=None, on_progress=None, on_frame=None):
    """Run ffmpeg, optionally reporting progress from the progress pipe.

    Chunk encoding reports frames with on_frame, because a chunk has no
    meaningful output duration until it finishes. The mux pass reports elapsed
    output time instead, via total_seconds and on_progress.
    """
    if _CANCELLED.is_set():
        raise RenderError("cancelled")

    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=NO_WINDOW,
    )
    with _ACTIVE_LOCK:
        _ACTIVE.add(process)
        if _CANCELLED.is_set():
            # Cancelled between the check and the spawn.
            process.kill()

    # stderr is drained on its own thread. Reading it only after stdout would
    # let a noisy failure fill the pipe buffer and block ffmpeg indefinitely.
    collected = []
    drain = threading.Thread(target=lambda: collected.append(process.stderr.read()))
    drain.daemon = True
    drain.start()

    if on_frame:
        for line in process.stdout:
            match = _FRAME_RE.match(line.strip())
            if match:
                on_frame(int(match.group(1)))
    elif on_progress and total_seconds:
        for line in process.stdout:
            match = _PROGRESS_RE.match(line.strip())
            if match:
                # Both out_time_us and out_time_ms carry microseconds.
                done = max(0.0, int(match.group(1)) / 1000000.0)
                on_progress(min(1.0, done / total_seconds))
    else:
        process.stdout.read()

    process.wait()
    with _ACTIVE_LOCK:
        _ACTIVE.discard(process)
    # The join is only a safety net against a wedged pipe. When the run is
    # being abandoned there is no point waiting on it at all.
    drain.join(timeout=0.1 if _CANCELLED.is_set() else 10)
    stderr = collected[0] if collected else ""
    if process.returncode != 0:
        tail = "\n".join(stderr.strip().splitlines()[-15:])
        raise RenderError("ffmpeg failed (exit %d):\n%s" % (process.returncode, tail))
    return stderr


def encode_chunk(tools, options, encoder, entries, output, on_frame=None):
    """Encode one contiguous run of images to an MPEG-TS part."""
    args = [tools.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats",
            "-progress", "pipe:1"]
    for entry in entries:
        args += ["-framerate", str(options["fps"]), "-i", entry["image"]]
    args += [
        "-filter_complex", chunk_filtergraph(entries, options, encoder["pix_fmt"]),
        "-map", "[v]",
        "-r", str(options["fps"]), "-fps_mode", "cfr",
        # The frame count is pinned here. This is what makes timing exact.
        "-frames:v", str(sum(entry["frames"] for entry in entries)),
        *encoder["args"],
        *COLOUR_TAGS,
        "-g", str(options["fps"] * 10),
        "-an", "-f", "mpegts", output,
    ]
    _run_ffmpeg(args, on_frame=on_frame)
    return output


def mux(tools, options, parts, job_dir, total_seconds, on_progress=None):
    """Join the encoded parts and lay the audio over them.

    The video is stream copied, so this pass only demuxes, concatenates and
    encodes the audio. It is cheap regardless of video length.
    """
    parts_list = write_concat_list(os.path.join(job_dir, "parts.ffconcat"), parts)
    audio_list = write_concat_list(os.path.join(job_dir, "audio.ffconcat"), options["audio"])
    _run_ffmpeg([
        tools.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-progress", "pipe:1", "-nostats",
        "-fflags", "+genpts",
        "-f", "concat", "-safe", "0", "-i", parts_list,
        "-f", "concat", "-safe", "0", "-i", audio_list,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        options["output"],
    ], total_seconds, on_progress)
    return options["output"]


def render(tools, options, encoder, timeline, job_dir, jobs, on_progress=None):
    """Encode every chunk, concurrently when there is more than one, then mux."""
    chunks = chunk_timeline(timeline, jobs, options["chunk_size"])
    total_seconds = timeline[-1]["end"]

    # Progress is aggregated from the frame counts every chunk reports while it
    # runs, so the bar moves continuously instead of jumping once per chunk.
    total_frames = sum(entry["frames"] for entry in timeline)
    encoded = {}
    counter_lock = threading.Lock()

    def report(number, frames):
        if not on_progress:
            return
        with counter_lock:
            encoded[number] = frames
            done = sum(encoded.values())
        on_progress(min(0.9, 0.9 * done / total_frames))

    def work(pair):
        number, entries = pair
        output = os.path.join(job_dir, "part_%04d.ts" % number)
        encode_chunk(tools, options, encoder, entries, output,
                     on_frame=lambda frames: report(number, frames))
        # Pin the chunk at its true total, in case the last progress line was
        # missed, so the bar cannot stall just short of the mux.
        report(number, sum(entry["frames"] for entry in entries))
        return number, output

    parts = []
    with ThreadPoolExecutor(max_workers=max(1, min(jobs, len(chunks)))) as pool:
        for result in pool.map(work, enumerate(chunks)):
            parts.append(result)

    parts.sort()
    # Encoding is the first 90 percent of the bar, the mux pass fills the rest.
    mux_progress = None
    if on_progress:
        def mux_progress(fraction):
            on_progress(0.9 + 0.1 * fraction)

    mux(tools, options, [path for _, path in parts], job_dir, total_seconds, mux_progress)
    if on_progress:
        on_progress(1.0)
    return options["output"]
