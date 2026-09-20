r"""Free up ports, disk space and leftovers, from a numbered menu.

    python backend\cli\cleanup.py

This is what Cleanup.bat runs. Everything it offers is safe in the sense that
matters: **no project is ever touched**. Narration, transcripts, images and
finished videos are the user's work and are never deleted here. What it clears
is what the app made for itself and can make again, plus the scratch folder.

Each item says how much space it is holding before you choose it, and asks
before it removes anything. Nothing happens on a bare Enter.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time

# This file lives in backend\cli\, and the i2v package sits in backend\.
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from api import processes  # noqa: E402
from console import can_prompt, confirm  # noqa: E402
from i2v import paths  # noqa: E402

API_PORT = 8765
WEB_PORT = 3000
STATE = os.path.join(paths.WORK, "start.json")

# Kept when the scratch folder is cleared: the rules file has to live there,
# and the checks and the contract are worth more than the space they take.
KEEP_IN_TEMP = ("claude-rules.md", "api-contract.md")
KEEP_PREFIXES = ("check_", "bench_")

_PORT_LINE = re.compile(r"^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$", re.IGNORECASE)


# --------------------------------------------------------------------------
# Looking
# --------------------------------------------------------------------------

def size_of(path):
    """Bytes held by a file or a folder, and how many files that is."""
    if os.path.isfile(path):
        try:
            return os.path.getsize(path), 1
        except OSError:
            return 0, 0
    total, count = 0, 0
    for folder, _, names in os.walk(path):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(folder, name))
                count += 1
            except OSError:
                pass
    return total, count


def spelled(size):
    for unit in ("bytes", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "%.0f %s" % (size, unit) if unit == "bytes" else "%.1f %s" % (size, unit)
        size /= 1024.0
    return "%.1f GB" % size


def listening(port):
    """The pid listening on a port, or None. netstat ships with Windows."""
    try:
        output = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True,
                                text=True, timeout=20,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in output.splitlines():
        match = _PORT_LINE.match(line)
        if match and int(match.group(1)) == port:
            return int(match.group(2))
    return None


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def name_of(pid):
    for row, _, exe in processes.table():
        if row == pid:
            return exe
    return "a program"


def running_state():
    """(pid, web url) the launcher left behind, if it is still running."""
    try:
        with open(STATE, "r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return None, None
    pid = state.get("pid")
    return (pid if isinstance(pid, int) and processes.alive(pid) else None), state.get("web")


def web_port():
    _, url = running_state()
    match = re.search(r":(\d+)", url or "")
    return int(match.group(1)) if match else WEB_PORT


# --------------------------------------------------------------------------
# The things that can be cleared
# --------------------------------------------------------------------------

def work(*parts):
    return os.path.join(paths.WORK, *parts)


ITEMS = [
    {
        "key": "media",
        "title": "Thumbnails, waveforms and preview audio",
        "note": "made again the moment they are needed",
        "paths": [work("thumbs"), work("peaks"), work("preview")],
    },
    {
        "key": "speech",
        "title": "Transcription cache",
        "note": "keeps a repeat of the same narration instant",
        "paths": [work("transcribe_cache")],
    },
    {
        "key": "encoder",
        "title": "The encoder choice",
        "note": "the encoders are timed again on the next build, a few seconds",
        "paths": [work(".encoder.json")],
    },
    {
        "key": "partial",
        "title": "Half finished uploads and renders",
        "note": "left behind only when something was interrupted",
        "paths": [work("uploads"), work("renders")],
        "extra": "jobs",
    },
    {
        "key": "trash",
        "title": "The trash",
        "note": "removed files are kept here for 7 days so they can be put back",
        "paths": [paths.TRASH],
    },
    {
        "key": "build",
        "title": "The web app's build",
        "note": "rebuilt the next time Run.bat starts, about a minute",
        "paths": [os.path.join(paths.FRONTEND, ".next")],
    },
    {
        "key": "packages",
        "title": "The web app's packages",
        "note": "Run.bat or Setup.bat installs them again, needs the internet",
        "paths": [os.path.join(paths.FRONTEND, "node_modules")],
    },
    {
        "key": "scratch",
        "title": "Scratch files in temp",
        "note": "keeps the rules file, the checks and the contract",
        "paths": [paths.ROOT and os.path.join(paths.ROOT, "temp")],
        "picked": True,
    },
]

REBUILDS = ("media", "encoder", "partial", "build")


def job_folders():
    """Leftover job_<pid> folders whose process is gone."""
    found = []
    try:
        names = os.listdir(paths.WORK)
    except OSError:
        return found
    for name in names:
        path = os.path.join(paths.WORK, name)
        if not name.startswith("job_") or not os.path.isdir(path):
            continue
        try:
            pid = int(name[4:])
        except ValueError:
            continue
        if not processes.alive(pid):
            found.append(path)
    return found


def scratch_files():
    """Everything in temp that is not worth keeping, as full paths."""
    folder = os.path.join(paths.ROOT, "temp")
    keep = set(KEEP_IN_TEMP)
    found = []
    try:
        names = os.listdir(folder)
    except OSError:
        return found
    for name in names:
        if name in keep or name.startswith(KEEP_PREFIXES):
            continue
        found.append(os.path.join(folder, name))
    return found


def targets(item):
    """The real paths this item would remove right now."""
    found = [path for path in item["paths"] if path and os.path.exists(path)]
    if item.get("picked"):
        found = scratch_files()
    if item.get("extra") == "jobs":
        found += job_folders()
    return found


def weigh(item):
    total, count = 0, 0
    for path in targets(item):
        bytes_here, files_here = size_of(path)
        total += bytes_here
        count += files_here
    return total, count


def remove(paths_to_remove):
    """Delete files and folders, returning how much was freed."""
    freed = 0
    for path in paths_to_remove:
        size, _ = size_of(path)
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            freed += size
        except OSError as error:
            print("      could not remove %s: %s" % (os.path.basename(path), error))
    return freed


# --------------------------------------------------------------------------
# Stopping the app
# --------------------------------------------------------------------------

def stop_app():
    """Stop img2vid and free its ports. Returns True if anything was stopped."""
    stopped = False
    pid, url = running_state()
    if pid:
        print("  stopping img2vid (process %d)" % pid)
        # Its Windows job object takes the web app and any ffmpeg with it.
        processes.kill(pid)
        for _ in range(20):
            if not processes.alive(pid):
                break
            time.sleep(0.25)
        stopped = True
    elif url:
        try:
            os.remove(STATE)
        except OSError:
            pass

    for port, what in ((API_PORT, "the engine"), (web_port(), "the web app")):
        if port_free(port):
            print("  port %d is free" % port)
            continue
        holder = listening(port)
        if not holder:
            print("  port %d is still busy, and nothing owns it. It clears on its own."
                  % port)
            continue
        print("  port %d is held by %s (process %d), which is not %s started by Run.bat"
              % (port, name_of(holder), holder, what))
        if confirm("  Stop that program?"):
            processes.kill(holder)
            time.sleep(0.5)
            print("  port %d is %s" % (port, "free" if port_free(port) else "still busy"))
        stopped = True
    return stopped


# --------------------------------------------------------------------------
# The menu
# --------------------------------------------------------------------------

def draw(weights):
    print()
    print("  img2vid cleanup")
    print("  " + "-" * 62)
    print("  Your projects are never touched here: narration, transcripts,")
    print("  images and finished videos are left exactly as they are.")
    print()
    pid, url = running_state()
    state = "running at %s" % url if pid else "not running"
    print("  %2d  %-40s %s" % (1, "Stop img2vid and free its ports", state))
    print("      %s" % "the ports are 8765 for the engine and 3000 for the web app")
    for number, item in enumerate(ITEMS, start=2):
        size, count = weights[item["key"]]
        held = "nothing to clear" if not count else "%s in %d file%s" % (
            spelled(size), count, "" if count == 1 else "s")
        print("  %2d  %-40s %s" % (number, item["title"], held))
        print("      %s" % item["note"])
    print("  %2d  %-40s %s" % (len(ITEMS) + 2, "Everything that rebuilds itself",
                               "items %s" % ", ".join(
                                   str(index + 2) for index, item in enumerate(ITEMS)
                                   if item["key"] in REBUILDS)))
    print("      %s" % "the safe ones, each still asked about on its own")
    print("   0  Quit")
    print()


def weigh_all():
    print("  working out what is being held", flush=True)
    return {item["key"]: weigh(item) for item in ITEMS}


def clear(item, weights):
    size, count = weights[item["key"]]
    if not count:
        print("  %s: nothing to clear." % item["title"])
        return False
    print()
    print("  %s" % item["title"])
    print("    %s in %d file%s, and %s"
          % (spelled(size), count, "" if count == 1 else "s", item["note"]))
    for path in targets(item)[:6]:
        print("      %s" % os.path.relpath(path, paths.ROOT))
    if len(targets(item)) > 6:
        print("      and %d more" % (len(targets(item)) - 6))
    if not confirm("  Remove them?"):
        print("  Nothing was removed.")
        return False
    freed = remove(targets(item))
    print("  freed %s" % spelled(freed))
    return True


def main(argv=None):
    if not can_prompt():
        print("  Cleanup needs a console to answer from. Double click Cleanup.bat.")
        return 2
    weights = weigh_all()
    while True:
        draw(weights)
        try:
            answer = input("  Choose 0 to %d:  " % (len(ITEMS) + 2)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if answer in ("0", "q", "quit", ""):
            print("  Nothing else was changed.")
            return 0
        if not answer.isdigit() or not 1 <= int(answer) <= len(ITEMS) + 2:
            print("  That is not one of the options.")
            continue
        choice = int(answer)
        if choice == 1:
            if not stop_app():
                print("  img2vid was not running.")
        elif choice == len(ITEMS) + 2:
            for item in ITEMS:
                if item["key"] in REBUILDS:
                    clear(item, weights)
                    weights[item["key"]] = weigh(item)
        else:
            item = ITEMS[choice - 2]
            clear(item, weights)
            weights[item["key"]] = weigh(item)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
