r"""Renames the images in input\images to 001, 002, 003 in date order.

The renderer takes the images in filename order, one per transcript line, so the
names are what decide which image lands on which line. Camera and download names
almost never sort the way the pictures were made:

    IMG_20260401_182233.jpg     screenshot (10).png     scene 2.jpeg

Those are put in the order they were created and renamed

    001.jpg                     002.png                 003.jpeg

Each file keeps its own extension, and anything in the folder that is not an
image is left alone. This is what Rename Images.bat calls.

Every run records what it did under temp\renames, so

    python app\rename_images.py --undo

puts the previous names back.
"""

import argparse
import json
import os
import sys
import time

# These launchers live in app\, so the project folder is the one above them.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from i2v import cli  # noqa: E402
from i2v.render import natural_key  # noqa: E402
from run import IMAGES, IMAGE_EXTENSIONS, _can_prompt, _confirm  # noqa: E402

TEMP = os.path.join(ROOT, "temp")
LOGS = os.path.join(TEMP, "renames")

# Long enough to be worth reading, short enough that the total and the answer to
# the prompt are both still on screen.
PREVIEW = 20

# The name a file holds between its old one and its new one.
HALFWAY = "__renaming__"


def build_parser():
    parser = argparse.ArgumentParser(
        prog="rename_images",
        description="Renumber the images in input\\images as 001, 002, 003 in date order.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-f", "--folder", default=IMAGES,
                        help="the folder to renumber")
    parser.add_argument("--by", default="created", choices=("created", "modified", "name"),
                        help="what to order the images by")
    parser.add_argument("--start", type=int, default=1,
                        help="the number the first image gets")
    parser.add_argument("--digits", type=int, default=3,
                        help="how many digits to pad to, 3 gives 001")
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would be renamed and change nothing")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="do not ask for confirmation")
    parser.add_argument("--undo", nargs="?", const="", default=None, metavar="RECORD",
                        help="put back the names from the previous run, or from a named"
                             " record under temp\\renames")
    return parser


def collect(folder, order):
    """Every image in the folder, in the order it will be numbered."""
    entries = []
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if not os.path.isfile(path) or not name.lower().endswith(IMAGE_EXTENSIONS):
            continue
        stat = os.stat(path)
        # st_ctime is the creation time on Windows, the one Explorer shows as
        # Date created. It is when the file arrived on this machine, so a folder
        # that was copied carries the time of the copy rather than the time the
        # picture was taken. --by modified is usually closer to that.
        entries.append({"name": name, "created": stat.st_ctime,
                        "modified": stat.st_mtime, "key": natural_key(name)})

    if order == "name":
        entries.sort(key=lambda entry: entry["key"])
    else:
        # Copying a folder stamps every file inside it with the same time, often
        # to the second, so the filename decides the order within a tie. Without
        # that the result would depend on the order the folder happens to list.
        entries.sort(key=lambda entry: (entry[order], entry["key"]))
    return entries


def plan(entries, digits, start):
    """Pair each current name with the name it should have."""
    # Widened rather than truncated, so 1200 images do not all collide at 999.
    highest = start + max(0, len(entries) - 1)
    width = max(digits, len(str(highest)))
    pairs = []
    for index, entry in enumerate(entries):
        extension = os.path.splitext(entry["name"])[1]
        pairs.append((entry["name"], "%0*d%s" % (width, start + index, extension)))
    return pairs


def free_name(folder, wanted):
    """A name nothing is using yet, for the halfway point of a rename."""
    candidate = HALFWAY + wanted
    counter = 2
    while os.path.exists(os.path.join(folder, candidate)):
        candidate = "%s%d__%s" % (HALFWAY, counter, wanted)
        counter += 1
    return candidate


def apply_plan(folder, pairs, trail):
    """Carry out the plan, recording each move so it can be undone.

    Two passes, through a temporary name. In one pass a file being renamed to
    002.jpg would collide with the file already called 002.jpg that has not had
    its own new number yet, and os.rename onto an existing name fails on
    Windows, which would leave the folder half renumbered.
    """
    staged = []
    for old, new in pairs:
        if old == new:
            continue
        halfway = free_name(folder, new)
        os.rename(os.path.join(folder, old), os.path.join(folder, halfway))
        trail.append([old, halfway])
        staged.append((halfway, new))

    for halfway, new in staged:
        os.rename(os.path.join(folder, halfway), os.path.join(folder, new))
        trail.append([halfway, new])
    return len(staged)


def write_log(folder, trail):
    """Record the moves so --undo has something to work from."""
    os.makedirs(LOGS, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    path = os.path.join(LOGS, stamp + ".json")
    # Two runs in the same second would otherwise overwrite the first record.
    counter = 2
    while os.path.exists(path):
        path = os.path.join(LOGS, "%s-%d.json" % (stamp, counter))
        counter += 1
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"folder": _stored(folder), "moves": trail}, handle, indent=2)
    return path


def _stored(folder):
    """Inside the project, keep the path relative so a moved copy can still undo."""
    try:
        relative = os.path.relpath(folder, ROOT)
    except ValueError:
        return folder
    return folder if relative.startswith("..") else relative


def _restored(folder):
    return folder if os.path.isabs(folder) else os.path.join(ROOT, folder)


def newest_log():
    """The most recent record that has not been undone already."""
    if not os.path.isdir(LOGS):
        return None
    names = sorted(name for name in os.listdir(LOGS) if name.endswith(".json")
                   and not name.endswith(".undone.json"))
    return os.path.join(LOGS, names[-1]) if names else None


def undo(wanted=None):
    path = os.path.abspath(wanted) if wanted else newest_log()
    if not path or not os.path.isfile(path):
        print()
        if wanted:
            print("  No such record: %s" % wanted)
        else:
            print("  Nothing to undo. No rename has been recorded yet.")
        print()
        return 2

    with open(path, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    folder = _restored(record["folder"])
    moves = record["moves"]

    print("  record    : %s" % os.path.relpath(path, ROOT))
    print("  folder    : %s" % _shown(folder))
    print()

    # Backwards, because the forward moves went through temporary names and the
    # last one out of a name has to be the first one back into it.
    restored = 0
    for source, destination in reversed(moves):
        current = os.path.join(folder, destination)
        original = os.path.join(folder, source)
        if not os.path.exists(current):
            print("  [!] %s is no longer there, skipped" % destination)
            continue
        if os.path.exists(original):
            print("  [!] %s is taken, skipped" % source)
            continue
        os.rename(current, original)
        # Every file moved twice on the way out, so only the step that lands on
        # a name of the user's own counts as a file put back.
        if not source.startswith(HALFWAY):
            restored += 1

    os.rename(path, path[:-len(".json")] + ".undone.json")
    wanted = sum(1 for source, _ in moves if not source.startswith(HALFWAY))
    print("  put back %d of %d names" % (restored, wanted))
    print()
    return 0 if restored else 1


def report(folder, pairs, order):
    changing = [(old, new) for old, new in pairs if old != new]
    print("  folder    : %s" % _shown(folder))
    print("  images    : %d" % len(pairs))
    print("  order     : %s" % {"created": "date created, oldest first",
                                "modified": "date modified, oldest first",
                                "name": "filename"}[order])
    print()
    for old, new in changing[:PREVIEW]:
        print("    %-40s ->  %s" % (_clipped(old, 40), new))
    if len(changing) > PREVIEW:
        print("    ... and %d more" % (len(changing) - PREVIEW))
    print()
    return changing


def _clipped(text, width):
    return text if len(text) <= width else text[:width - 3] + "..."


def _shown(folder):
    """The folder as the user knows it, which is a path inside the project."""
    try:
        return os.path.relpath(folder, ROOT)
    except ValueError:
        return folder


def explain_setup(folder):
    print()
    print("  Nothing to rename.")
    print("    missing: images in %s\\" % _shown(folder))
    print()
    print("  Put your images there, then run this again. Any names will do,")
    print("  this is what puts them in order.")
    print()


def main(argv=None):
    args = build_parser().parse_args(argv)

    print()
    print("  rename images")
    print("  " + "-" * 60)

    if args.undo is not None:
        return undo(args.undo or None)

    folder = os.path.abspath(args.folder)
    # Made rather than reported missing, for the same reason the step files make
    # it: a folder the instructions point at should be there to be opened.
    os.makedirs(folder, exist_ok=True)

    entries = collect(folder, args.by)
    if not entries:
        explain_setup(folder)
        return 2

    pairs = plan(entries, max(1, args.digits), args.start)
    changing = report(folder, pairs, args.by)

    if not changing:
        print("  Already numbered in that order. Nothing to do.")
        print()
        return 0

    if args.dry_run:
        print("  Nothing was renamed, this was --dry-run.")
        print()
        return 0

    if not args.yes:
        if not _can_prompt():
            print("  Add --yes to rename without a question to answer.")
            print()
            return 2
        if not _confirm("  Rename %d files?" % len(changing)):
            print("  Nothing was renamed.")
            print()
            return 2
        print()

    trail = []
    try:
        renamed = apply_plan(folder, pairs, trail)
    except OSError:
        # A record is written here too, not only on success. A folder left part
        # renumbered is exactly when being able to put the names back matters.
        if trail:
            print("  stopped partway, %d files were renamed" % _files_in(trail))
            _undo_hint(write_log(folder, trail))
        raise

    print("  renamed %d of %d images" % (renamed, len(pairs)))
    if trail:
        _undo_hint(write_log(folder, trail))
    print()
    print("  Next: run Create Video.bat")
    print()
    return 0


def _files_in(trail):
    return sum(1 for source, _ in trail if not source.startswith(HALFWAY))


def _undo_hint(record):
    print("  undo with : Rename Images.bat --undo")
    print("  record    : %s" % os.path.relpath(record, ROOT))


if __name__ == "__main__":
    cli.install_interrupt_handler()
    try:
        sys.exit(main())
    except OSError as error:
        sys.stderr.write("\nerror: %s\n" % error)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.stderr.write("\ncancelled\n")
        sys.exit(130)
