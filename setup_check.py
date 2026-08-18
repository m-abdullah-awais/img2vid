r"""Prove that a freshly set up copy of img2vid actually works.

Setup.bat runs this at the end. It renders a tiny video from material it
generates itself, then checks the result frame by frame, so a setup that
reports success really can produce a correct video on this machine.

Everything it writes goes in temp\setup_check and is deleted afterwards.
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

WORK = os.path.join(ROOT, "temp", "setup_check")
FPS = 30
TOTAL = 4.0
# Deliberately not a whole number of frames apart, so the frame quantiser is
# actually exercised rather than trivially satisfied.
STARTS = [0.0, 1.37, 2.9]
COLOURS = ["red", "green", "blue"]

_failures = []


def check(label, ok, detail=""):
    print("     %s %s%s" % ("[x]" if ok else "[!]", label, ("  " + detail) if detail else ""))
    if not ok:
        _failures.append(label)


def clock(seconds):
    whole = int(seconds)
    return "%02d:%02d:%02d,%03d" % (whole // 3600, (whole % 3600) // 60, whole % 60,
                                    int(round((seconds - whole) * 1000)))


def main():
    print("     python      %s" % sys.version.split()[0])

    try:
        from i2v import probe, render, transcript
    except ImportError as error:
        check("img2vid modules import", False, str(error))
        return 1
    check("img2vid modules import", True)

    try:
        tools = probe.Tools(ROOT)
    except probe.ProbeError as error:
        check("ffmpeg and ffprobe found", False, str(error))
        return 1
    where = "bin" if tools.ffmpeg.lower().startswith(os.path.join(ROOT, "bin").lower()) else "PATH"
    check("ffmpeg and ffprobe found", True, "using %s" % where)

    # ctypes drives the guard that stops encoders when the window is closed.
    guarded = probe.bind_children_to_this_process()
    check("child process guard available", guarded or os.name != "nt",
          "" if guarded else "not active, encoders may outlive a closed window")

    shutil.rmtree(WORK, ignore_errors=True)
    images_dir = os.path.join(WORK, "images")
    os.makedirs(images_dir, exist_ok=True)

    try:
        for index, colour in enumerate(COLOURS, start=1):
            subprocess.run([
                tools.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=%s:s=640x360" % colour,
                "-frames:v", "1", os.path.join(images_dir, "%d.png" % index),
            ], check=True, creationflags=probe.NO_WINDOW)
        subprocess.run([
            tools.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=%s" % TOTAL,
            "-ac", "2", os.path.join(WORK, "audio.wav"),
        ], check=True, creationflags=probe.NO_WINDOW)
    except (subprocess.CalledProcessError, OSError) as error:
        check("ffmpeg can generate media", False, str(error))
        return 1
    check("ffmpeg can generate media", True)

    ends = STARTS[1:] + [TOTAL]
    with open(os.path.join(WORK, "script.srt"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(
            "%d\n%s --> %s\nLine %d\n" % (i + 1, clock(a), clock(b), i + 1)
            for i, (a, b) in enumerate(zip(STARTS, ends))))

    encoder = probe.detect_encoder(tools, "auto", os.path.join(ROOT, "temp"))
    check("an H.264 encoder works", True, "%s selected" % encoder["codec"])

    output = os.path.join(WORK, "out.mp4")
    result = subprocess.run([
        sys.executable, os.path.join(ROOT, "img2vid.py"),
        "-t", os.path.join(WORK, "script.srt"),
        "-i", images_dir,
        "-a", os.path.join(WORK, "audio.wav"),
        "-o", output, "--size", "640x360", "--quiet",
    ], capture_output=True, text=True)
    if result.returncode != 0:
        check("renders a video end to end", False,
              (result.stderr or result.stdout).strip()[-300:])
        return 1
    check("renders a video end to end", True)

    expected_frames = round(TOTAL * FPS)
    probed = subprocess.run([
        tools.ffprobe, "-v", "error", "-count_frames", "-select_streams", "v",
        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", output,
    ], capture_output=True, text=True, creationflags=probe.NO_WINDOW).stdout.strip()
    check("frame count is exact", probed == str(expected_frames),
          "%s frames, expected %d" % (probed or "none", expected_frames))

    audio_ok = subprocess.run([
        tools.ffprobe, "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=codec_name", "-of", "csv=p=0", output,
    ], capture_output=True, text=True, creationflags=probe.NO_WINDOW).stdout.strip()
    check("audio track present", audio_ok == "aac", audio_ok or "none")

    # One pixel per frame, so the image boundaries are checked rather than assumed.
    raw = subprocess.run([
        tools.ffmpeg, "-v", "error", "-i", output,
        "-vf", "crop=iw/4:ih/4:iw*3/8:ih*3/8,scale=1:1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ], capture_output=True, creationflags=probe.NO_WINDOW).stdout
    seq = [tuple(raw[i:i + 3]) for i in range(0, len(raw) - 2, 3)]
    runs = []
    for colour in seq:
        if runs and runs[-1][0] == colour:
            runs[-1][1] += 1
        else:
            runs.append([colour, 1])
    boundaries = [0] + [round(v * FPS) for v in STARTS[1:]] + [round(TOTAL * FPS)]
    wanted = [boundaries[i + 1] - boundaries[i] for i in range(len(STARTS))]
    check("each image is shown for the right number of frames",
          [n for _, n in runs] == wanted,
          "got %s, expected %s" % ([n for _, n in runs], wanted))

    shutil.rmtree(WORK, ignore_errors=True)

    if _failures:
        print()
        print("     %d check(s) failed." % len(_failures))
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
