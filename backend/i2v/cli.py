"""Command line interface for img2vid."""

import argparse
import os
import shutil
import signal
import sys
import time

from . import __version__, captions, paths, probe, render, transcript

DEFAULTS = {
    "fps": 30,
    "size": "1920x1080",
    "fit": "contain",
    "background": "black",
    "encoder": "auto",
}

# Quick Sync is one fixed function engine. A couple of sessions keep it fed;
# more than that just queue up and add scheduling overhead.
QSV_MAX_JOBS = 3

# libx264 already threads across every core on its own, so running one process
# per core oversubscribes the CPU and measures slower than running fewer.
# Best of 3 runs, 100 images at 1080p30 on 8 cores:
#   1 job 40.3s, 2 jobs 41.3s, 4 jobs 37.2s, 8 jobs 43.5s
# Half the cores was both the fastest and by far the most consistent.
CORES_PER_SOFTWARE_JOB = 2


def build_parser():
    parser = argparse.ArgumentParser(
        prog="img2vid",
        description=(
            "Build a video from a timestamped transcript, one image per "
            "transcript line, and one or more audio files. Each image is held "
            "from its own timestamp until the next one. The last image runs "
            "until the audio ends."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-t", "--transcript", required=True,
                        help="SRT, VTT, or plain text with line leading timestamps")
    parser.add_argument("-i", "--images", required=True,
                        help="folder of images, one per transcript line. Numbered names "
                             "place each image on the line it is numbered for, and a line "
                             "with no image is black. Otherwise natural filename order")
    parser.add_argument("-a", "--audio", required=True, nargs="+",
                        help="one or more audio files, joined in the order given")
    parser.add_argument("-o", "--output", default="output.mp4", help="output MP4 path")

    parser.add_argument("--fps", type=int, default=DEFAULTS["fps"], help="output frame rate")
    parser.add_argument("--size", default=DEFAULTS["size"], help="output resolution, WIDTHxHEIGHT")
    parser.add_argument("--fit", choices=["contain", "cover"], default=DEFAULTS["fit"],
                        help="contain letterboxes the image, cover crops it to fill")
    parser.add_argument("--bg", dest="background", default=DEFAULTS["background"],
                        help="letterbox colour used by --fit contain")

    parser.add_argument("--captions", action="store_true",
                        help="burn each transcript line into the picture while it is "
                             "spoken. Off unless asked for, and it costs encoding time")
    parser.add_argument("--caption-place", choices=sorted(captions.PLACES), default="bottom",
                        help="where the captions sit in the frame")
    parser.add_argument("--caption-distance", type=float, default=8.0,
                        help="how far the captions sit from that edge, as a percentage "
                             "of the frame height. Ignored in the middle")
    parser.add_argument("--caption-size", choices=sorted(captions.SIZES), default="medium",
                        help="caption text size, as a share of the frame height")
    parser.add_argument("--caption-look", choices=sorted(captions.BORDERS), default="outline",
                        help="outline reads on any picture, band puts the text on a "
                             "dark strip for busy artwork")
    parser.add_argument("--caption-font", default="Arial",
                        help="the font the captions are set in, by name")

    parser.add_argument("--jobs", type=int, default=0,
                        help="concurrent encoder processes, 0 chooses a sensible number")
    parser.add_argument("--chunk-size", type=int, default=render.CHUNK_SIZE,
                        help="images per encoder process")
    parser.add_argument("--encoder", choices=["auto", "qsv", "x264"], default=DEFAULTS["encoder"],
                        help="auto times both encoders once and caches the faster one")

    parser.add_argument("--force", action="store_true",
                        help="build the video even if the images and timestamps do not "
                             "line up, instead of stopping. Extra images are ignored, "
                             "extra timestamps are absorbed by the last image")
    parser.add_argument("--allow-black", action="store_true",
                        help="build the video even when some transcript lines have no "
                             "image, showing a black screen for those lines. Deliberately "
                             "separate from --force, which is safe to leave permanently on")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the resolved timeline and exit without encoding")
    parser.add_argument("--keep-temp", action="store_true",
                        help="keep the intermediate files in backend/storage/work")
    parser.add_argument("--quiet", action="store_true", help="suppress progress output")
    parser.add_argument("--version", action="version", version="img2vid " + __version__)
    return parser


def parse_size(value):
    try:
        width, height = value.lower().split("x")
        width, height = int(width), int(height)
    except ValueError:
        raise SystemExit("Invalid --size %r. Use WIDTHxHEIGHT, for example 1920x1080." % value)
    if width < 16 or height < 16:
        raise SystemExit("Invalid --size %r. Both dimensions must be at least 16." % value)
    # H.264 needs even dimensions, and Quick Sync is strict about it.
    return width - (width % 2), height - (height % 2)


def choose_jobs(requested, encoder_name, chunk_count):
    """Pick how many encoder processes to run at once.

    Neither encoder wants one process per core. See the constants above for the
    measurements behind each cap.
    """
    if requested > 0:
        return max(1, min(requested, chunk_count))
    cores = os.cpu_count() or 4
    if encoder_name == "qsv":
        jobs = min(cores, QSV_MAX_JOBS)
    else:
        jobs = max(1, cores // CORES_PER_SOFTWARE_JOB)
    return max(1, min(jobs, chunk_count))


def listed(missing, limit=12):
    """The missing line numbers, clipped.

    A folder a hundred images short should not print a hundred numbers at
    somebody, and the count is stated alongside this anyway.
    """
    shown = ", ".join(str(number) for number in missing[:limit])
    if len(missing) > limit:
        shown += ", and %d more" % (len(missing) - limit)
    return shown


def these_lines(count):
    """The three ways this message has to refer to the lines with no image.

    Worth the few lines, because "1 transcript line(s) have no image" is the
    first thing a user reads when a run stops, and it should read like a
    sentence somebody wrote.
    """
    if count == 1:
        return "1 transcript line has", "that line", "the missing image"
    return ("%d transcript lines have" % count, "those %d lines" % count,
            "the %d missing images" % count)


def missing_images_error(missing):
    """The stop, when lines have no image and nobody has said black is fine.

    Black frames are a real edit to the video, so they are offered rather than
    assumed. The point worth making in the message is that nothing has shifted:
    the whole cost of saying no is running this again with the images added.
    """
    have, those, add = these_lines(len(missing))
    return render.RenderError(
        "%s no image: %s.\n"
        "  Images are placed by the number their filename starts with, so nothing\n"
        "  else has moved out of place. Add %s to the images folder\n"
        "  and run again, or build the video now and leave %s as a\n"
        "  black screen.\n"
        "Pass --allow-black to build it with %s black."
        % (have, listed(missing), add, those, those),
        repair="--allow-black",
        question="Leave %s black and build the video?" % those)


def black_lines_note(missing):
    """Say which lines are coming out black, once that has been agreed to."""
    have = these_lines(len(missing))[0]
    return ("%s no image and will be black: %s.\n"
            "           Images are placed by the number their filename starts with,\n"
            "           so every other line still matches the narration."
            % (have, listed(missing)))


def print_timeline(timeline, total_audio, fps, encoder_name, jobs, chunks):
    print("  #  image                                          start        end     dur   frames")
    print("  " + "-" * 83)
    for entry in timeline:
        print("%3d  %-44s %8.3f %10.3f %7.3f %8d" % (
            entry["index"] + 1,
            ("(black, no image)" if entry["black"]
             else os.path.basename(entry["image"]))[:44],
            entry["start"], entry["end"], entry["seconds"], entry["frames"],
        ))
    frames = sum(entry["frames"] for entry in timeline)
    print("  " + "-" * 83)
    print("  segments: %d   audio: %.3fs   video: %.3fs   frames: %d @ %d fps"
          % (len(timeline), total_audio, frames / fps, frames, fps))
    print("  encoder: %s   chunks: %d   jobs: %d" % (encoder_name, chunks, jobs))


def make_progress(quiet):
    if quiet:
        return None
    state = {"last": -1.0, "start": time.time()}

    def report(fraction):
        percent = fraction * 100
        if percent - state["last"] < 1.0 and fraction < 1.0:
            return
        state["last"] = percent
        filled = int(fraction * 30)
        sys.stderr.write("\r  [%s%s] %5.1f%%  %4.1fs" % (
            "#" * filled, "." * (30 - filled), percent, time.time() - state["start"]))
        sys.stderr.flush()

    return report


def main(argv=None):
    args = build_parser().parse_args(argv)
    started = time.time()

    temp_root = paths.WORK
    os.makedirs(temp_root, exist_ok=True)

    # If this process dies, for any reason including the console window being
    # closed, the encoders must die with it rather than run on orphaned.
    probe.bind_children_to_this_process()
    probe.sweep_stale_jobs(temp_root)

    for path in [args.transcript] + args.audio:
        if not os.path.isfile(path):
            raise SystemExit("File not found: %s" % path)
    if args.fps < 1:
        raise SystemExit("--fps must be at least 1.")
    if args.chunk_size < 1:
        raise SystemExit("--chunk-size must be at least 1.")

    tools = probe.Tools(paths.BIN)
    width, height = parse_size(args.size)

    lines = transcript.parse(args.transcript)
    starts = [start for start, _ in lines]
    texts = [text for _, text in lines]
    images = render.find_images(args.images)
    total_audio = probe.total_duration(tools, args.audio)
    def warn(text):
        sys.stderr.write("  warning: %s\n" % text)
        sys.stderr.flush()

    # A numbered image names the transcript line it belongs to, so one that was
    # never made leaves that line black rather than pulling every later image
    # forward a line and running the rest of the video against the wrong words.
    placed = render.place_by_index(images, len(starts))
    if placed is not None:
        images, missing = placed
        # --dry-run is exempt because showing what would happen is its whole
        # job, and --quiet is not, because this is a stop rather than a remark.
        if missing and not args.allow_black and not args.dry_run:
            raise missing_images_error(missing)
        if missing and not args.quiet:
            warn(black_lines_note(missing))

    timeline = render.build_timeline(
        starts, images, total_audio, args.fps,
        force=args.force, on_warning=None if args.quiet else warn, texts=texts)

    notify = None if args.quiet else (lambda text: print(text, flush=True))
    encoder = probe.detect_encoder(tools, args.encoder, temp_root, notify)
    jobs = choose_jobs(args.jobs, encoder["name"], len(timeline))
    chunks = len(render.chunk_timeline(timeline, jobs, args.chunk_size))
    jobs = min(jobs, chunks)

    if args.dry_run:
        print_timeline(timeline, total_audio, args.fps, encoder["name"], jobs, chunks)
        return 0

    options = {
        "fps": args.fps, "width": width, "height": height,
        "fit": args.fit, "background": args.background,
        "chunk_size": args.chunk_size,
        "audio": [os.path.abspath(item) for item in args.audio],
        "output": os.path.abspath(args.output),
        # None unless asked for, which is what keeps a plain render exactly as
        # fast as it was before captions existed.
        "captions": {"place": args.caption_place,
                     "distance": max(0.0, args.caption_distance) / 100.0,
                     "size": args.caption_size, "look": args.caption_look,
                     "font": args.caption_font} if args.captions else None,
    }
    output_dir = os.path.dirname(options["output"])
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    job_dir = os.path.join(temp_root, "job_%d" % os.getpid())
    os.makedirs(job_dir, exist_ok=True)
    progress = make_progress(args.quiet)

    if not args.quiet:
        total_frames = sum(entry["frames"] for entry in timeline)
        print("  %d images, %.1fs audio, %s at %dx%d %dfps"
              % (len(timeline), total_audio, encoder["codec"], width, height, args.fps),
              flush=True)
        print("  encoding %d frames in %d chunks over %d parallel jobs"
              % (total_frames, chunks, jobs), flush=True)

    try:
        render.render(tools, options, encoder, timeline, job_dir, jobs, progress)
    finally:
        if not args.keep_temp:
            shutil.rmtree(job_dir, ignore_errors=True)

    if not args.quiet:
        sys.stderr.write("\n")
        total_seconds = timeline[-1]["end"]
        size_mb = os.path.getsize(options["output"]) / (1024 * 1024)
        print("  done in %.1fs  ->  %s  (%.1f MB, %.3fs, %.1fx realtime)"
              % (time.time() - started, options["output"], size_mb, total_seconds,
                 total_seconds / max(1e-6, time.time() - started)))
    return 0


def install_interrupt_handler():
    """Stop the encoders the moment Ctrl+C is pressed.

    Without this the interrupt is not acted on until the chunk in flight
    finishes, because the worker threads are blocked reading ffmpeg output.
    Killing the processes first unblocks them, so the pool shuts down at once.
    """
    def handler(signum, frame):
        render.terminate_active()
        raise KeyboardInterrupt

    # SIGBREAK is Ctrl+Break on Windows. Without it that key combination skips
    # Python entirely and the process is torn down by the operating system,
    # which works but skips the temp cleanup and the cancelled message.
    names = ["SIGINT", "SIGBREAK", "SIGTERM"]
    for name in names:
        received = getattr(signal, name, None)
        if received is None:
            continue
        try:
            signal.signal(received, handler)
        except (ValueError, OSError, RuntimeError):
            pass


def run():
    install_interrupt_handler()
    try:
        sys.exit(main())
    except (transcript.TranscriptError, render.RenderError, probe.ProbeError) as error:
        render.terminate_active()
        sys.stderr.write("\nerror: %s\n" % error)
        sys.exit(1)
    except KeyboardInterrupt:
        render.terminate_active()
        sys.stderr.write("\ncancelled\n")
        sys.exit(130)
