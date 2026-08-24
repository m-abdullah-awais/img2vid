r"""Zero argument speech to text for img2vid.

Turns the audio sitting in the input folder into a timestamped transcript, which
is exactly what the video step then needs. This is what Transcribe Audio.bat
calls, so there is nothing to type.

    input\
      audio\              one or more audio files, joined in name order

Writes three files, all describing the same cues:

    input\script.srt      the transcript the renderer reads
    input\script.txt      the same thing, readable at a glance
    temp\script.json      start, end and text, for any other tool

One cue becomes one image, so the number of cues is the number of images the
video needs. Use --max-chars or --max-seconds to control that count.

Any extra arguments are passed through, so this still works:

    python app\transcribe.py --model small --max-chars 90
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

# These launchers live in app\, so the project folder is the one above them.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from i2v import captions, cli, probe, speech  # noqa: E402
from run import AUDIO, AUDIO_EXTENSIONS, IMAGES, INPUT, OUTPUT, _can_prompt, listing  # noqa: E402

TEMP = os.path.join(ROOT, "temp")
CACHE = os.path.join(TEMP, "transcribe_cache")
REPLACED = os.path.join(TEMP, "replaced")

# Whisper resamples to 16 kHz mono anyway, so joining several files at that rate
# does the conversion once instead of twice.
JOIN_RATE = 16000


def build_parser():
    parser = argparse.ArgumentParser(
        prog="transcribe",
        description="Turn the audio in input\\audio into a timestamped transcript.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-a", "--audio", nargs="+",
                        help="audio files, defaults to everything in input\\audio")
    parser.add_argument("--pick", action="store_true",
                        help="choose which audio file to use instead of joining them all")
    parser.add_argument("--name", default="script",
                        help="base name for the written files")
    parser.add_argument("--out-dir", default=INPUT,
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
                        help="keep the intermediate files in temp/")
    parser.add_argument("--quiet", action="store_true", help="suppress progress output")
    return parser


def explain_setup():
    print()
    print("  Nothing to transcribe yet.")
    print("    missing: audio in input\\audio\\")
    print()
    print("  Put your narration here, then run this again:")
    print()
    print("    input\\audio\\          one or more audio files, joined in name order")
    print()
    print("  The transcript is written to input\\script.srt, ready for Create Video.bat.")
    print()


def discover():
    """Audio files in natural order, from input\\audio or loose in input."""
    # input\images and output are made here too, even though this step writes to
    # neither, because the count this run reports is the number of images the
    # user then has to drop into input\images. Being sent to a folder that does
    # not exist is the point at which people assume the tool is broken.
    for folder in (INPUT, AUDIO, IMAGES, OUTPUT, TEMP):
        os.makedirs(folder, exist_ok=True)
    return listing(AUDIO, AUDIO_EXTENSIONS) or listing(INPUT, AUDIO_EXTENSIONS)


def choose_audio(found):
    """Offer the choice between joining every file and using just one.

    Joining is the default because the renderer joins the same files in the same
    order, so a joined transcript lines up with the video. Picking one is what
    you want when the folder holds takes or alternatives rather than parts.
    """
    print()
    print("  Which audio should be transcribed?")
    print()
    print("    a) all %d files, joined into one continuous transcript" % len(found))
    for index, path in enumerate(found, start=1):
        print("    %d) %s" % (index, os.path.basename(path)))
    print()
    while True:
        try:
            answer = input("  Choose a number, or a for all [a] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return found
        if answer in ("", "a", "all"):
            return found
        if answer.isdigit() and 1 <= int(answer) <= len(found):
            return [found[int(answer) - 1]]
        print("  That is not one of the options.")


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
    replaced. Anything already under temp/ is a byproduct of a previous run and
    is left alone, otherwise every run would archive its own output.
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

    audio = args.audio or discover()
    if not audio:
        explain_setup()
        return 2
    for path in audio:
        if not os.path.isfile(path):
            raise SystemExit("File not found: %s" % path)

    if not args.audio and len(audio) > 1:
        if args.pick and _can_prompt():
            audio = choose_audio(audio)
        elif args.pick:
            print("  --pick needs a console to answer from, joining all %d files"
                  % len(audio))
        else:
            print("  joining all %d audio files, add --pick to choose just one"
                  % len(audio))

    probe.bind_children_to_this_process()
    probe.sweep_stale_jobs(TEMP)
    tools = probe.Tools(ROOT)
    duration = probe.total_duration(tools, audio)

    for index, path in enumerate(audio):
        print("  audio %-5s: %s" % (index + 1, os.path.relpath(path, ROOT)))
    print("  duration   : %.1fs" % duration)

    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    targets = {
        "srt": os.path.join(out_dir, args.name + ".srt"),
        "txt": os.path.join(out_dir, args.name + ".txt"),
        "json": os.path.join(TEMP, args.name + ".json"),
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
            source = audio[0]
            if len(audio) > 1:
                os.makedirs(job, exist_ok=True)
                print("  joining %d audio files into one continuous track" % len(audio),
                      flush=True)
                source = join_audio(tools, audio, os.path.join(job, "narration.wav"))

            report = cli.make_progress(args.quiet)
            notify = None if args.quiet else (lambda text: print(text, flush=True))
            raw, info = speech.transcribe(
                ROOT, source, duration=duration, model=args.model,
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
    print("  Next: put %d images in input\\images\\ then run Create Video.bat" % len(cues))
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
