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
import struct
import subprocess
import threading
import zlib
from concurrent.futures import ThreadPoolExecutor

from . import captions
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
_LEADING_NUMBER = re.compile(r"\d+")
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
    """Raised when inputs do not line up or ffmpeg fails.

    `repair` is the one flag that would let this particular run carry on, and
    `question` is what to ask before adding it. Create Video.bat uses the pair
    to offer that flag on a double click, where there is nowhere to type one.

    Both stay None for a failure no flag can put right, which is what stops the
    offer being made for something like a missing images folder, where saying
    yes only produces the same failure a second time.
    """

    def __init__(self, message, repair=None, question=None):
        super().__init__(message)
        self.repair = repair
        self.question = question


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


def shown_name(image):
    """A path's filename, or a stand in for a line that has no image."""
    return os.path.basename(image) if image else "(black)"


def place_by_index(images, count):
    """Put every image on the transcript line its own filename numbers.

    Pairing by position has no error detection in it. An image that was never
    made is not a hole in the list, it is an absence, so every later image
    slides one line earlier and the video runs against the wrong narration from
    that point on. The only symptom is a count one short, which says nothing
    about where the gap is or which lines are now wrong.

    A number in a filename is an identity rather than a position, so 004.jpg
    means line four whether or not 003.jpg exists. A line that no image claims
    comes back as None, and is rendered as a black frame for its full duration,
    which leaves every other line exactly where it belongs.

    Returns None when the folder is not numbered this way, and the caller pairs
    by position as before. That takes every name starting with a number, and no
    name claiming a line past the end of the transcript. The second condition
    is what keeps camera names out: 20260401_182233.jpg claims line twenty
    million, so a folder of those is paired by position exactly as it always
    was. Two names claiming one line is an error rather than a fallback,
    because by then the folder is plainly numbered and only one of them can be
    right.
    """
    report = placement_report(images, count)
    if report["mode"] != "numbered":
        return None
    if report["duplicates"]:
        clash = report["duplicates"][0]
        raise RenderError(
            "Two images both claim line %d: %s and %s.\n"
            "Images are placed by the number their filename starts with, so "
            "one number cannot be used twice. Rename one of them."
            % (clash["number"], clash["names"][0], clash["names"][1])
        )
    return report["slots"], report["missing"]


def placement_report(images, count):
    """Everything place_by_index decides, without raising and with the reasons.

    place_by_index only needs a yes or no, but a screen showing the folder has
    to say why a folder is paired by position, name the file that caused it,
    and list every clash rather than stopping at the first. Returns a dict:

        mode        "numbered", "positional", or "empty" when there are no images
        reason      None, or {"kind", "name", "number"} naming the file that sent
                    the folder to position: "unnumbered" when its name has no
                    leading number, "past_end" when its number is beyond the
                    last line, "no_lines" when there is no transcript to number
        base        0 or 1 when numbered, else None
        slots       one path or None per line when numbered, else None. A line
                    two images claim holds the first of them
        missing     the numbers no image claims, when numbered
        duplicates  [{"number", "names"}] for every number claimed twice or more
    """
    report = {"mode": "positional", "reason": None, "base": None, "slots": None,
              "missing": [], "duplicates": []}
    if not images:
        report["mode"] = "empty"
        return report
    if count < 1:
        report["reason"] = {"kind": "no_lines", "name": None, "number": None}
        return report

    numbers = []
    for path in images:
        match = _LEADING_NUMBER.match(os.path.basename(path))
        if not match:
            report["reason"] = {"kind": "unnumbered", "name": os.path.basename(path),
                                "number": None}
            return report
        numbers.append(int(match.group()))

    # The rename tool can number a folder from 000 with --start 0, and that
    # is as valid a scheme as one starting at 001. A zero present says which.
    base = 0 if 0 in numbers else 1
    highest = max(numbers)
    if highest - base >= count:
        report["reason"] = {"kind": "past_end",
                            "name": os.path.basename(images[numbers.index(highest)]),
                            "number": highest}
        return report

    claimed = {}
    for number, path in zip(numbers, images):
        claimed.setdefault(number, []).append(path)

    slots = [None] * count
    for number, paths in claimed.items():
        slots[number - base] = paths[0]
    report.update(
        mode="numbered", base=base, slots=slots,
        missing=[index + base for index, path in enumerate(slots) if path is None],
        duplicates=[{"number": number, "names": [os.path.basename(p) for p in paths]}
                    for number, paths in sorted(claimed.items()) if len(paths) > 1])
    return report


# --------------------------------------------------------------------------
# The black frame
# --------------------------------------------------------------------------

def _png_chunk(tag, payload):
    """One length, tag, payload and CRC record, which is all a PNG is made of."""
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff))


def black_image(path, width, height):
    """Write a solid black PNG at exactly the output resolution.

    At the output size rather than at some small size on purpose. Then --fit
    contain has nothing to pad and --fit cover has nothing to crop, so the
    frame comes out black whatever --bg is set to and whatever shape the real
    images happen to be.

    Written here rather than fetched from an imaging library because the whole
    video side of this project is standard library only, and a solid colour PNG
    is a header and one deflate stream. A 1080p field of zeros compresses to a
    few kilobytes in a few milliseconds.
    """
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    # Filter byte 0 then three zero bytes per pixel, for every row.
    body = zlib.compress((b"\x00" + b"\x00\x00\x00" * width) * height, 6)
    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(_png_chunk(b"IHDR", header))
        handle.write(_png_chunk(b"IDAT", body))
        handle.write(_png_chunk(b"IEND", b""))
    return path


def fill_black(timeline, job_dir, width, height):
    """Give every line with no image the same black frame, and return how many.

    One file shared by all of them. ffmpeg decodes each input once and holds
    the frame with the loop filter, so a hundred black lines cost one decode
    of one small file each and nothing else.
    """
    empty = [entry for entry in timeline if entry["image"] is None]
    if empty:
        path = black_image(os.path.join(job_dir, "black.png"), width, height)
        for entry in empty:
            entry["image"] = path
    return len(empty)


# --------------------------------------------------------------------------
# Timeline
# --------------------------------------------------------------------------

def build_timeline(starts, images, total_audio, fps, force=False, on_warning=None,
                   texts=None):
    """Pair each image with an exact whole number of frames.

    Every boundary is rounded to a frame once and shared by the segments on
    both sides of it, so rounding error cannot accumulate and the frame counts
    add up to exactly round(total_audio * fps).

    The first image is pulled back to time zero even if the transcript starts
    later, so the video never opens on black.

    An image of None is a line that no image claimed, which place_by_index
    produces when the folder is numbered and one of the numbers is absent. It
    is kept in the timeline with its own frame count and marked black, so the
    line holds a black frame for its full duration and every later line stays
    where it belongs. fill_black turns it into a real file before encoding.

    Three things can make the inputs unusable: the counts not matching, audio
    that stops before the last timestamp, and two timestamps closer together
    than a single frame. Normally each is a hard error, because silently
    guessing would produce a mistimed video that looks fine until you watch it.
    With force set, each is repaired instead and reported through on_warning.

    `texts` is what each line says, carried through so captions can be burned
    into the picture later. It follows every repair above, so a line that is
    dropped takes its words with it.
    """
    warn = on_warning or (lambda text: None)
    texts = list(texts) if texts else [""] * len(starts)
    texts += [""] * (len(starts) - len(texts))

    # 1. One image per timestamp.
    if len(images) != len(starts):
        if not force:
            raise RenderError(
                "Count mismatch: %d transcript timestamps but %d images.\n"
                "  first images: %s\n"
                "There must be exactly one image per timestamp.\n"
                "Name each image for the line it belongs to, 1 to %d, and any line\n"
                "left without one is rendered black instead of shifting the rest.\n"
                "Pass --force to build the video anyway from whichever there are fewer of."
                % (
                    len(starts),
                    len(images),
                    ", ".join(shown_name(item) for item in images[:5]) or "none",
                    len(starts),
                ),
                repair="--force",
                question="Build the video anyway, ignoring the mismatch?",
            )
        keep = min(len(images), len(starts))
        if not keep:
            raise RenderError("Nothing to render: no images or no timestamps.")
        if len(images) > keep:
            warn("--force: %d timestamps but %d images. Ignoring the last %d image(s): %s"
                 % (len(starts), len(images), len(images) - keep,
                    ", ".join(shown_name(item) for item in images[keep:][:5])))
        else:
            warn("--force: %d timestamps but %d images. Using the first %d timestamps, "
                 "so image %d holds until the audio ends."
                 % (len(starts), len(images), keep, keep))
        starts, images, texts = starts[:keep], images[:keep], texts[:keep]

    # 2. The audio has to outlast the final timestamp, since the last image is
    #    held until the audio ends.
    if total_audio <= starts[-1]:
        if not force:
            raise RenderError(
                "The audio is %.3fs long but the last transcript timestamp is at "
                "%.3fs. The audio must run past the final timestamp.\n"
                "Pass --force to drop the timestamps that fall past the end of the audio."
                % (total_audio, starts[-1]),
                repair="--force",
                question="Drop the timestamps past the end of the audio and build it?",
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
        starts, images, texts = starts[:keep], images[:keep], texts[:keep]

    # 3. Quantise to whole frames. The first boundary is pinned to zero so the
    #    video never opens on black.
    end_boundary = round(total_audio * fps)
    pairs = []
    dropped = 0
    for index, (start, image, text) in enumerate(zip(starts, images, texts)):
        boundary = 0 if index == 0 else round(start * fps)
        if pairs and boundary <= pairs[-1][0]:
            if not force:
                raise RenderError(
                    "Timestamps %d and %d are less than one frame apart at %d fps "
                    "(%.3fs and %.3fs). Increase --fps or merge the lines.\n"
                    "Pass --force to drop the shorter of the two."
                    % (index, index + 1, fps, starts[index - 1], start),
                    repair="--force",
                    question="Drop the shorter of those two lines and build the video?",
                )
            dropped += 1
            continue
        pairs.append((boundary, image, text))

    if end_boundary <= pairs[-1][0]:
        # The final image would get no frames at all.
        if not force or len(pairs) == 1:
            raise RenderError(
                "The last timestamp at %.3fs leaves no room before the audio ends "
                "at %.3fs.%s"
                % (pairs[-1][0] / fps, total_audio,
                   "" if force else "\nPass --force to drop that line."),
                repair=None if force else "--force",
                question="Drop that last line and build the video?",
            )
        dropped += 1
        pairs.pop()

    if dropped:
        warn("--force: dropped %d line(s) shorter than one frame at %d fps." % (dropped, fps))

    timeline = []
    for index, (boundary, image, text) in enumerate(pairs):
        following = pairs[index + 1][0] if index + 1 < len(pairs) else end_boundary
        timeline.append({
            "index": index,
            "image": image,
            "text": text,
            "black": image is None,
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


def chunk_captions(entries, options, stem):
    """Write one caption file per line of this chunk, and name them in order.

    One file per line, rather than one for the whole chunk, because of where the
    filter then goes. A line's words are the same for every frame its image is
    held for, so the caption is drawn onto the single decoded frame before the
    loop filter repeats it. The text is then rasterised and blended once per
    image instead of once per frame: measured on a 3.5 minute video, that is the
    difference between captions costing 26 percent and costing almost nothing.

    Returns a list with one file name per entry, None where a line has no words,
    or None in place of the whole list when nothing is captioned.
    """
    settings = options.get("captions")
    if not settings:
        return None
    style = captions.caption_style(options["width"], options["height"], **settings)
    names = []
    for position, entry in enumerate(entries):
        text = (entry.get("text") or "").strip()
        if not text:
            names.append(None)
            continue
        path = "%s_%02d.ass" % (stem, position)
        # The frame this is drawn on sits at time zero, and the cue has to cover
        # it. The end only has to be past zero; the picture's own frame count is
        # what decides how long the line stays on screen.
        cue = [{"start": 0.0, "end": max(1.0, entry["seconds"]), "text": text}]
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(captions.to_ass(cue, style))
        names.append(os.path.basename(path))
    return names if any(names) else None


def chunk_filtergraph(entries, options, pix_fmt, subtitles=None):
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
        # Drawn on the one decoded frame, before loop repeats it, so the words
        # are rasterised once per image rather than once per frame. The file is
        # named without a path because ffmpeg runs from the folder holding it:
        # a Windows drive colon inside a filter argument would need escaping
        # through two levels of parsing, and every path here contains a space.
        caption = subtitles[position] if subtitles else None
        chains.append(
            "[%d:v]format=rgb24,%s,setsar=1,%s%s,format=%s,"
            "loop=loop=%d:size=1:start=0,setpts=N/FR/TB[v%d]"
            % (position, geometry, "subtitles=%s," % caption if caption else "",
               COLOUR_CONVERSION, pix_fmt, entry["frames"] - 1, position)
        )
        labels.append("[v%d]" % position)
    chains.append("%sconcat=n=%d:v=1:a=0[v]" % ("".join(labels), len(entries)))
    return ";".join(chains)


# --------------------------------------------------------------------------
# ffmpeg execution
# --------------------------------------------------------------------------

def _run_ffmpeg(args, total_seconds=None, on_progress=None, on_frame=None, cwd=None):
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
        cwd=cwd,
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
    job_dir = os.path.dirname(os.path.abspath(output))
    subtitles = chunk_captions(entries, options, os.path.splitext(output)[0])
    args = [tools.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats",
            "-progress", "pipe:1"]
    for entry in entries:
        args += ["-framerate", str(options["fps"]), "-i", entry["image"]]
    args += [
        "-filter_complex",
        chunk_filtergraph(entries, options, encoder["pix_fmt"], subtitles),
        "-map", "[v]",
        "-r", str(options["fps"]), "-fps_mode", "cfr",
        # The frame count is pinned here. This is what makes timing exact.
        "-frames:v", str(sum(entry["frames"] for entry in entries)),
        *encoder["args"],
        *COLOUR_TAGS,
        "-g", str(options["fps"] * 10),
        "-an", "-f", "mpegts", output,
    ]
    # From the job folder, which is what lets the caption file above be named
    # without a path. Every other file here is given absolutely.
    _run_ffmpeg(args, on_frame=on_frame, cwd=job_dir)
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
    fill_black(timeline, job_dir, options["width"], options["height"])
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
