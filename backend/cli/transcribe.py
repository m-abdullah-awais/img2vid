r"""Speech to text for img2vid.

Turns one or more audio files into a timestamped transcript, which is exactly
what the video step then needs. This is what the web app runs when a project's
narration is transcribed.

    python backend\cli\transcribe.py -a part1.wav part2.wav --out-dir <folder>

Several files are joined in the order given, so the timestamps run on across
them the same way the video joins them. Writes three files into --out-dir, all
describing the same cues:

    script.srt      the transcript the renderer reads
    script.txt      the same thing, readable at a glance
    script.json     start, end and text, for any other tool

One cue becomes one image, so the number of cues is the number of images the
video needs. Use --max-chars or --max-seconds to control that count.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

# These scripts live in backend\cli\, and the i2v package sits in backend\.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from i2v import captions, cli, paths, probe, speech  # noqa: E402

ROOT = paths.ROOT
TEMP = paths.WORK
CACHE = os.path.join(TEMP, "transcribe_cache")
REPLACED = os.path.join(TEMP, "replaced")

# Whisper resamples to 16 kHz mono anyway, so joining several files at that rate
# does the conversion once instead of twice.
JOIN_RATE = 16000


def build_parser():
    parser = argparse.ArgumentParser(
        prog="transcribe",
        description="Turn narration audio into a timestamped transcript.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-a", "--audio", nargs="+", required=True,
                        help="one or more audio files, joined in the order given")
    parser.add_argument("--name", default="script",
                        help="base name for the written files")
    parser.add_argument("--out-dir", required=True,
                        help="where the transcript is written")

    parser.add_argument("--model", default=speech.DEFAULT_MODEL, choices=speech.MODEL_SIZES,
                        help="larger is more accurate and slower")
    parser.add_argument("--language", default=None,
                        help="force a language code such as en, default is auto detect")
    parser.add_argument("--beam", type=int, default=1,
                        help="beam width, 1 is greedy and fastest")
    parser.add_argument("--batch", type=int, default=0,
                        help="decode this many speech regions at once, 0 is sequential")
    parser.add_argument("--threads", type=int, default=0,
                        help="CPU threads for the decoder, 0 lets the engine choose")
    parser.add_argument("--compute", default="int8",
                        help="numeric precision, int8 is fast and light on a CPU")
    parser.add_argument("--words", action="store_true",
                        help="also record a timestamp for every word")
    parser.add_argument("--condition", action="store_true",
                        help="feed each segment the previous text, slower and can loop")

    parser.add_argument("--max-chars", type=int, default=0,
                        help="split cues longer than this many characters, 0 is off")
    parser.add_argument("--max-seconds", type=float, default=0.0,
                        help="split cues longer than this many seconds, 0 is off")
    parser.add_argument("--min-seconds", type=float, default=0.0,
                        help="merge cues shorter than this many seconds, 0 is off")

    parser.add_argument("--fresh", action="store_true",
                        help="ignore the cached result for this audio")
    parser.add_argument("--keep-temp", action="store_true",
                        help="keep the intermediate files in backend/storage/work")
    parser.add_argument("--quiet", action="store_true", help="suppress progress output")
    return parser


def join_audio(tools, paths, destination):
    """Concatenate several files into one 16 kHz mono WAV.

    The concat filter is used rather than the demuxer because the inputs can be
    any mix of formats and sample rates. Joining first is what keeps timestamps
    continuous across files instead of restarting at zero on each one.
    """
    args = [tools.ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    for path in paths:
        args += ["-i", path]
    args += [
        "-filter_complex",
        "%sconcat=n=%d:v=0:a=1[out]" % ("".join("[%d:a]" % i for i in range(len(paths))),
                                        len(paths)),
        "-map", "[out]", "-ar", str(JOIN_RATE), "-ac", "1", "-c:a", "pcm_s16le",
        destination,
    ]
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace",
                            creationflags=probe.NO_WINDOW)
    if result.returncode != 0 or not os.path.isfile(destination):
        raise speech.SpeechError("Could not join the audio files.\n  %s"
                                 % result.stderr.strip())
    return destination


def stash(path):
    """Copy an existing file aside before it is overwritten, and say where.

    A transcript can represent a lot of manual correction, so it is never simply
    replaced. Anything already under the work folder is a byproduct of a
    previous run and is left alone, otherwise every run would archive its own
    output.
    """
    if not os.path.isfile(path):
        return None
    if os.path.abspath(path).startswith(os.path.abspath(TEMP) + os.sep):
        return None
    os.makedirs(REPLACED, exist_ok=True)
    stem, extension = os.path.splitext(os.path.basename(path))
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = os.path.join(REPLACED, "%s.%s%s" % (stem, stamp, extension))
    # Two runs in the same second would otherwise overwrite the first backup.
    counter = 2
    while os.path.exists(backup):
        backup = os.path.join(REPLACED, "%s.%s-%d%s" % (stem, stamp, counter, extension))
        counter += 1
    shutil.copy2(path, backup)
    return backup


def load_cached(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def main(argv=None):
    args = build_parser().parse_args(argv)
    started = time.time()

    # Any reshaping needs to know where the words are, so ask for word timings
    # rather than guessing a split point.
    reshaping = args.max_chars > 0 or args.max_seconds > 0 or args.min_seconds > 0
    word_timestamps = args.words or reshaping

    print()
    print("  transcribe")
    print("  " + "-" * 60)

    audio = args.audio
    for path in audio:
        if not os.path.isfile(path):
            raise SystemExit("File not found: %s" % path)

    os.makedirs(TEMP, exist_ok=True)
    probe.bind_children_to_this_process()
    probe.sweep_stale_jobs(TEMP)
    tools = probe.Tools(paths.BIN)
    duration = probe.total_duration(tools, audio)

    for index, path in enumerate(audio):
        print("  audio %-5s: %s" % (index + 1, os.path.relpath(path, ROOT)))
    print("  duration   : %.1fs" % duration)

    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    targets = {
        "srt": os.path.join(out_dir, args.name + ".srt"),
        "txt": os.path.join(out_dir, args.name + ".txt"),
        "json": os.path.join(out_dir, args.name + ".json"),
    }
    print("  output     : %s" % os.path.relpath(targets["srt"], ROOT))

    options = {"model": args.model, "language": args.language, "beam": args.beam,
               "batch": args.batch, "compute": args.compute, "condition": args.condition,
               "words": word_timestamps}
    key = speech.signature(audio, options)
    cache_file = os.path.join(CACHE, key + ".json")

    raw = None if args.fresh else load_cached(cache_file)
    job = os.path.join(TEMP, "job_%d" % os.getpid())

    try:
        if raw is not None:
            print("  cached     : reusing an earlier transcription of this audio")
        else:
            report = cli.make_progress(args.quiet)
            notify = None if args.quiet else (lambda text: print(text, flush=True))

            # Before the audio is touched, not after. Joining a dozen files takes
            # half a minute, and finding out at the end of it that the model was
            # never downloaded means that work is thrown away for nothing.
            if not speech.model_is_local(paths.RUNTIME, args.model):
                print("  model      : %s is not on this machine yet, fetching it first"
                      % args.model, flush=True)
                speech.download(paths.RUNTIME, args.model, on_message=notify)

            source = audio[0]
            if len(audio) > 1:
                os.makedirs(job, exist_ok=True)
                print("  joining %d audio files into one continuous track" % len(audio),
                      flush=True)
                source = join_audio(tools, audio, os.path.join(job, "narration.wav"))

            raw, info = speech.transcribe(
                paths.RUNTIME, source, duration=duration, model=args.model,
                language=args.language, beam_size=args.beam,
                word_timestamps=word_timestamps, condition=args.condition,
                batch_size=args.batch, compute_type=args.compute,
                cpu_threads=args.threads, on_progress=report, on_message=notify,
            )
            if not args.quiet:
                sys.stderr.write("\n")
                if info.get("language"):
                    print("  language   : %s" % info["language"])
            os.makedirs(CACHE, exist_ok=True)
            captions.write(cache_file, raw, "json")
    finally:
        if not args.keep_temp:
            shutil.rmtree(job, ignore_errors=True)

    cues = captions.resplit(raw, args.max_chars, args.max_seconds, args.min_seconds)
    if reshaping:
        print("  reshaped   : %d cues -> %d" % (len(raw), len(cues)))

    for kind, path in targets.items():
        backup = stash(path)
        captions.write(path, cues, kind)
        if backup:
            print("  replaced   : %s  (kept as %s)"
                  % (os.path.relpath(path, ROOT), os.path.relpath(backup, ROOT)))

    elapsed = max(1e-6, time.time() - started)
    print("  done in %.1fs  ->  %s  (%d cues, %.1fx realtime)"
          % (elapsed, os.path.relpath(targets["srt"], ROOT), len(cues), duration / elapsed))
    print()
    print("  Next: add %d images, one for each line, then build the video" % len(cues))
    print()
    return 0


if __name__ == "__main__":
    cli.install_interrupt_handler()
    try:
        sys.exit(main())
    except (speech.SpeechError, probe.ProbeError) as error:
        sys.stderr.write("\nerror: %s\n" % error)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.stderr.write("\ncancelled\n")
        sys.exit(130)
