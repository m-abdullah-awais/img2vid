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
    print("    input\\images\\         one image per transcript line, named 1, 2, 3 ...")
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

    try:
        return main(argv + passed)
    except RenderError as error:
        # Double clicking leaves no way to add a flag, so offer it here instead
        # of making the user edit Create Video.bat and start over.
        if "--force" in passed or not _can_prompt():
            raise
        print()
        print("  %s" % str(error).splitlines()[0])
        print()
        if not _confirm("  Build the video anyway, ignoring the mismatch?"):
            print("  Nothing was rendered.")
            return 1
        print()
        return main(argv + passed + ["--force"])


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
