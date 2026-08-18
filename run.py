r"""Zero argument launcher for img2vid.

Discovers everything from the `input` folder and renders, so there is nothing
to type. This is what Run.bat calls.

    input\
      script.srt          the transcript, any of .srt .vtt .txt
      images\             one image per transcript line
      audio\              one or more audio files

The result is written to `output\<transcript name>.mp4`.

Any extra arguments are passed straight through to the renderer, so this still
works:

    python run.py --fps 10
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
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

    transcripts = listing(INPUT, TRANSCRIPT_EXTENSIONS)
    images = listing(IMAGES, IMAGE_EXTENSIONS)
    # Audio may sit in input\audio, or loose in input alongside the transcript.
    audio = listing(AUDIO, AUDIO_EXTENSIONS) or listing(INPUT, AUDIO_EXTENSIONS)

    missing = []
    if not transcripts:
        missing.append("a transcript in input\\  (.srt, .vtt or .txt)")
    if not images:
        missing.append("images in input\\images\\")
    if not audio:
        missing.append("audio in input\\audio\\")
    if missing:
        explain_setup(missing)
        return None

    return transcripts[0], IMAGES, audio


def run():
    print()
    print("  img2vid")
    print("  " + "-" * 60)

    found = discover()
    if not found:
        # 2 means "nothing to do yet", as opposed to 1 for a real failure.
        return 2
    transcript, images, audio = found

    name = os.path.splitext(os.path.basename(transcript))[0]
    output = os.path.join(OUTPUT, name + ".mp4")

    print("  transcript : %s" % os.path.relpath(transcript, ROOT))
    print("  images     : %s (%d files)" % (os.path.relpath(images, ROOT),
                                            len(listing(images, IMAGE_EXTENSIONS))))
    for index, item in enumerate(audio):
        print("  audio %-5s: %s" % (index + 1, os.path.relpath(item, ROOT)))
    print("  output     : %s" % os.path.relpath(output, ROOT))
    print(flush=True)

    argv = ["-t", transcript, "-i", images, "-a", *audio, "-o", output]
    passed = sys.argv[1:]

    from i2v.render import RenderError  # noqa: PLC0415

    try:
        return main(argv + passed)
    except RenderError as error:
        # Double clicking leaves no way to add a flag, so offer it here instead
        # of making the user edit Run.bat and start over.
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


def _confirm(question):
    try:
        answer = input("%s [y/N] " % question)
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.strip().lower() in ("y", "yes")


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
