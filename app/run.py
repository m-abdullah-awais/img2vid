r"""Zero argument launcher for img2vid.

Discovers everything from the `input` folder and renders, so there is nothing
to type. This is what Create Video.bat calls.

    input\
      script.srt          the transcript, any of .srt .vtt .txt
      images\             one image per transcript line
      audio\              one or more audio files

The result is written to `output\<date>_<time>.mp4`, so a new render never
overwrites the last one and the folder sorts oldest first.

Any extra arguments are passed straight through to the renderer, so this still
works:

    python app\run.py --fps 10
"""

import os
import sys
import time

# These launchers live in app\, so the project folder is the one above them.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from i2v.cli import main  # noqa: E402
from i2v.render import natural_key  # noqa: E402

INPUT = os.path.join(ROOT, "input")
IMAGES = os.path.join(INPUT, "images")
AUDIO = os.path.join(INPUT, "audio")
OUTPUT = os.path.join(ROOT, "output")

TRANSCRIPT_EXTENSIONS = (".srt", ".vtt", ".txt")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma")

# Videos are named for when they were made, not for the transcript. The
# transcript is nearly always called script.srt, so naming the video after it
# meant every render produced output\script.mp4 and silently replaced the one
# before it. A timestamp keeps every take, and sorts oldest first in Explorer.
# Pass -o to choose the name yourself.
OUTPUT_NAME = "%Y-%m-%d_%H-%M-%S"


def listing(folder, extensions):
    """Files in a folder with the given extensions, in natural filename order."""
    if not os.path.isdir(folder):
        return []
    names = [
        name for name in os.listdir(folder)
        if name.lower().endswith(extensions)
        and os.path.isfile(os.path.join(folder, name))
    ]
    names.sort(key=natural_key)
    return [os.path.join(folder, name) for name in names]


def explain_setup(missing):
    print()
    print("  Nothing to render yet.")
    for item in missing:
        print("    missing: %s" % item)
    print()
    print("  Put your files here, then run this again:")
    print()
    print("    input\\script.srt      your timestamped transcript (.srt, .vtt or .txt)")
    print("    input\\images\\         one per transcript line, named 1, 2, 3 for the")
    print("                          line it belongs to. A missing one is black")
    print("    input\\audio\\          one or more audio files, joined in name order")
    print()
    print("  The finished video is written to the output folder.")
    print()


def discover():
    """Return (transcript, images_folder, audio_files) or None with an explanation."""
    for folder in (INPUT, IMAGES, AUDIO, OUTPUT):
        os.makedirs(folder, exist_ok=True)

    # After transcribing there is a readable .txt sitting next to the .srt, so
    # take the formats in preference order rather than whichever sorts first.
    transcripts = []
    for extension in TRANSCRIPT_EXTENSIONS:
        transcripts = listing(INPUT, (extension,))
        if transcripts:
            break
    images = listing(IMAGES, IMAGE_EXTENSIONS)
    # Audio may sit in input\audio, or loose in input alongside the transcript.
    audio = listing(AUDIO, AUDIO_EXTENSIONS) or listing(INPUT, AUDIO_EXTENSIONS)

    missing = []
    if not transcripts:
        missing.append("a transcript in input\\  (.srt, .vtt or .txt)"
                       "  -> run Transcribe Audio.bat to make one")
    if not images:
        missing.append("images in input\\images\\")
    if not audio:
        missing.append("audio in input\\audio\\")
    if missing:
        explain_setup(missing)
        return None

    return transcripts[0], IMAGES, audio


def chosen_output(passed):
    """The output path the user asked for on the command line, if any."""
    for index, item in enumerate(passed):
        if item in ("-o", "--output"):
            return passed[index + 1] if index + 1 < len(passed) else None
        if item.startswith("--output="):
            return item.split("=", 1)[1]
        # argparse also accepts a short option glued to its value.
        if item.startswith("-o") and len(item) > 2 and not item.startswith("--"):
            return item[2:]
    return None


def run():
    print()
    print("  img2vid")
    print("  " + "-" * 60)

    found = discover()
    if not found:
        # 2 means "nothing to do yet", as opposed to 1 for a real failure.
        return 2
    transcript, images, audio = found

    passed = sys.argv[1:]
    # An -o on the command line wins, because it is appended after this one and
    # argparse keeps the last. Read it here too, so the line printed below is
    # the file that will actually be written rather than the name we made up.
    output = chosen_output(passed) or os.path.join(
        OUTPUT, time.strftime(OUTPUT_NAME) + ".mp4")

    print("  transcript : %s" % os.path.relpath(transcript, ROOT))
    print("  images     : %s (%d files)" % (os.path.relpath(images, ROOT),
                                            len(listing(images, IMAGE_EXTENSIONS))))
    for index, item in enumerate(audio):
        print("  audio %-5s: %s" % (index + 1, os.path.relpath(item, ROOT)))
    print("  output     : %s" % os.path.relpath(output, ROOT))
    print(flush=True)

    argv = ["-t", transcript, "-i", images, "-a", *audio, "-o", output]

    from i2v.render import RenderError  # noqa: PLC0415

    # Double clicking leaves no way to add a flag, so a failure that one flag
    # would put right is offered here instead of making the user edit this file
    # and start over. Which flag, and what to ask, comes from the failure
    # itself: offering --force for a missing images folder only produced the
    # same failure a second time.
    extra = []
    while True:
        try:
            return main(argv + passed + extra)
        except RenderError as error:
            repair = getattr(error, "repair", None)
            if not repair or repair in passed or repair in extra or not _can_prompt():
                raise
            print()
            for line in _offer_lines(error):
                print("  %s" % line)
            print()
            if not _confirm("  " + error.question):
                print("  Nothing was rendered.")
                return 1
            print()
            # Appended before the retry, so each flag can only be offered once
            # and the loop cannot spin. A second, different problem still gets
            # its own offer, which the single retry this replaced could not do.
            extra.append(repair)


def _offer_lines(error):
    """The failure, as told to somebody who is about to be offered the fix.

    The last line of these messages names the flag that repairs them, which is
    right on a command line and wrong here, because the next thing printed is
    that same offer as a question.
    """
    return [line for line in str(error).splitlines() if not line.startswith("Pass ")]


def _can_prompt():
    """Only offer a prompt when there is a real console to answer from."""
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _confirm(question, default_yes=False):
    """Ask a yes or no question. The capital letter is what Enter does.

    default_yes is for the questions that only confirm the thing the user
    already asked for. It stays off for anything that overrides a check, where
    Enter has to mean no.
    """
    prompt = "%s [Y/n] " if default_yes else "%s [y/N] "
    try:
        answer = input(prompt % question).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    if not answer:
        return default_yes
    return answer in ("y", "yes")


if __name__ == "__main__":
    from i2v import probe, render, transcript as transcript_module
    from i2v.cli import install_interrupt_handler

    install_interrupt_handler()
    try:
        sys.exit(run())
    except (transcript_module.TranscriptError, render.RenderError, probe.ProbeError) as error:
        # One chunk failing leaves the others still encoding. Stop them.
        render.terminate_active()
        sys.stderr.write("\nerror: %s\n" % error)
        sys.exit(1)
    except KeyboardInterrupt:
        render.terminate_active()
        sys.stderr.write("\ncancelled\n")
        sys.exit(130)
