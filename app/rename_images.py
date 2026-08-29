r"""Renames the images in input\images to 001, 002, 003 in date order.

The renderer takes the images in filename order, one per transcript line, so the
names are what decide which image lands on which line. Camera and download names
almost never sort the way the pictures were made:

    IMG_20260401_182233.jpg     screenshot (10).png     scene 2.jpeg

Those are put in the order they were created and renamed

    001.jpg                     002.png                 003.jpeg

Each file keeps its own extension, and anything in the folder that is not an
image is left alone. This is what Rename Images.bat calls.

The order is not fixed. Sort by date created, date modified, filename, file
size, file type or at random, forwards or reversed:

    python app\rename_images.py --by size --desc
    python app\rename_images.py --by random --seed 7

An image can also be dropped into the middle of the sequence. Put a new picture
at number 5 and everything from 5 onward shifts up one, then the whole folder is
renumbered:

    python app\rename_images.py --insert "C:\shots\new.png" --at 5

A file from outside is copied in, so the original stays where it was. A file
already in the folder is moved within the order instead. Double clicking the
batch file offers the same thing as a question, since there is nowhere to type
a flag.

Every run records what it did under temp\renames, so

    python app\rename_images.py --undo

puts the previous names back.
"""

import argparse
import json
import os
import random
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

# What a folder of images can be put in order by, and how each one reads when
# it is reversed. Everything else in the file works off these keys, so adding an
# order means adding a row here and a sort in collect().
ORDERS = {
    "created":  ("date created, oldest first",   "date created, newest first"),
    "modified": ("date modified, oldest first",  "date modified, newest first"),
    "name":     ("filename, A to Z",             "filename, Z to A"),
    "size":     ("file size, smallest first",    "file size, largest first"),
    "type":     ("file type, then filename",     "file type reversed, then filename"),
    "random":   ("random shuffle",               "random shuffle"),
}


def order_label(order, desc, seed=None):
    label = ORDERS[order][1 if desc else 0]
    if order == "random" and seed is not None:
        return "%s, seed %d  (repeat it with --seed %d)" % (label, seed, seed)
    return label


# The name a copied in image holds until the renumber gives it its real one.
# It also marks the move in the record, so --undo deletes the copy instead of
# renaming it back to a staging name that meant nothing to the user.
INSERTED = "__inserted__"


def build_parser():
    parser = argparse.ArgumentParser(
        prog="rename_images",
        description="Renumber the images in input\\images as 001, 002, 003 in date order.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-f", "--folder", default=IMAGES,
                        help="the folder to renumber")
    parser.add_argument("--by", default="created", choices=tuple(ORDERS),
                        help="what to order the images by")
    parser.add_argument("--desc", "--reverse", dest="desc", action="store_true",
                        help="reverse it, so the last one becomes 001")
    parser.add_argument("--seed", type=int, default=None,
                        help="the seed for --by random, so a shuffle can be repeated")
    parser.add_argument("--start", type=int, default=1,
                        help="the number the first image gets")
    parser.add_argument("--digits", type=int, default=3,
                        help="how many digits to pad to, 3 gives 001")
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would be renamed and change nothing")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="do not ask for confirmation")
    parser.add_argument("--insert", action="append", default=None, metavar="IMAGE",
                        help="an image to put into the sequence, by path or by name."
                             " Repeat it, once per --at")
    parser.add_argument("--at", action="append", type=int, default=None, metavar="N",
                        help="the number the image before it should end up at")
    parser.add_argument("--undo", nargs="?", const="", default=None, metavar="RECORD",
                        help="put back the names from the previous run, or from a named"
                             " record under temp\\renames")
    return parser


def find_source(folder, given):
    """Locate an image the user named, wherever they meant it.

    Accepts a full path, a path relative to where they are, or a bare filename
    that is already sitting in the images folder. Explorer and the console both
    hand over dragged paths wrapped in quotes, so those come off first.
    """
    wanted = given.strip().strip('"').strip("'")
    if not wanted:
        return None, "no name given"
    candidates = [wanted, os.path.join(folder, wanted)]
    for candidate in candidates:
        path = os.path.abspath(candidate)
        if os.path.isfile(path):
            if not path.lower().endswith(IMAGE_EXTENSIONS):
                return None, "%s is not an image" % os.path.basename(path)
            return path, None
    return None, "cannot find %s" % wanted


def stage_inserts(folder, sources):
    """Bring each image into the folder under a name nothing else is using.

    A file that already lives in the folder is left where it is and only moved
    in the ordering. One from anywhere else is copied rather than moved, so the
    user's original is still where they left it.
    """
    import shutil  # noqa: PLC0415

    staged = []
    for path in sources:
        inside = os.path.dirname(path).lower() == folder.lower()
        if inside:
            staged.append({"name": os.path.basename(path), "label": os.path.basename(path),
                           "copied": False})
            continue
        extension = os.path.splitext(path)[1]
        # Not free_name, which prefixes with HALFWAY. The INSERTED prefix is what
        # tells --undo this file was copied in and should be deleted, not renamed.
        name = INSERTED + "%d%s" % (len(staged), extension)
        counter = 2
        while os.path.exists(os.path.join(folder, name)):
            name = INSERTED + "%d_%d%s" % (len(staged), counter, extension)
            counter += 1
        shutil.copy2(path, os.path.join(folder, name))
        staged.append({"name": name, "label": os.path.basename(path), "copied": True})
    return staged


def place(entries, staged, positions):
    """Put each staged image at the number the user asked for.

    Positions are the numbers shown to the user, so 1 is the first image. They
    are applied in the order given, and each one is clamped to the sequence as
    it stands at that moment, so asking for 99 in a folder of 20 appends.
    """
    ordered = [dict(entry) for entry in entries]
    for item, wanted in zip(staged, positions):
        # A file already in the folder is being moved, not added, so it has to
        # come out of its old place before it goes into the new one.
        ordered = [entry for entry in ordered if entry["name"] != item["name"]]
        index = max(0, min(len(ordered), wanted - 1))
        ordered.insert(index, {"name": item["name"], "label": item["label"],
                               "inserted": True, "created": 0, "modified": 0,
                               "key": natural_key(item["name"])})
    return ordered


def ask_for_order(order, desc):
    """Ask what to put the images in order by, and which way round."""
    keys = list(ORDERS)
    print()
    print("  Put them in order by:")
    print()
    for index, key in enumerate(keys, start=1):
        mark = "  (now)" if key == order else ""
        print("    %d) %-9s %s%s" % (index, key, ORDERS[key][0], mark))
    print()
    try:
        answer = input("  Choose 1 to %d [%d]: " % (len(keys), keys.index(order) + 1)).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return order, desc
    if answer.isdigit() and 1 <= int(answer) <= len(keys):
        order = keys[int(answer) - 1]

    if order == "random":
        # There is no other way round a shuffle, so do not ask.
        return order, False
    return order, _confirm("  Reverse it, so the last one becomes 001?")


def ask_what_to_do(folder, count, order, desc):
    """Offer the things a double click cannot ask for on a command line.

    Answering nothing is the ordinary renumber, which is what almost every run
    wants, so the common case is still a single press of Enter.
    """
    print("  images    : %d in %s" % (count, _shown(folder)))
    print("  order     : %s" % order_label(order, desc))
    print()
    print("    1) renumber them in this order       (just press Enter)")
    print("    2) insert an image at a number, then renumber")
    print("    3) put them in a different order first")
    print()
    try:
        choice = input("  Choose 1, 2 or 3 [1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return [], [], order, desc

    if choice == "3":
        order, desc = ask_for_order(order, desc)
        print()
        print("  order     : %s" % order_label(order, desc))
        try:
            if not _confirm("  Insert an image as well?"):
                return [], [], order, desc
        except (EOFError, KeyboardInterrupt):
            return [], [], order, desc
    elif choice != "2":
        return [], [], order, desc

    inserts, positions = _ask_for_inserts(folder, count)
    return inserts, positions, order, desc


def _ask_for_inserts(folder, count):
    """Collect image and position pairs until the user stops giving them."""

    inserts, positions = [], []
    while True:
        total = count + len(inserts) + 1
        print()
        try:
            given = input("  Image to insert, or leave blank to finish: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not given:
            break
        path, problem = find_source(folder, given)
        if problem:
            print("  %s" % problem)
            continue
        try:
            where = input("  Put it at which number? 1 to %d: " % total).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not where.isdigit() or int(where) < 1:
            print("  That is not a number, so it was skipped.")
            continue
        inserts.append(path)
        positions.append(min(int(where), total))
        print("  %s becomes number %d" % (os.path.basename(path), positions[-1]))
    print()
    return inserts, positions


def discard_staged(folder, staged):
    """Remove the copies made for an insert that is not going ahead."""
    for item in staged:
        if not item.get("copied"):
            continue
        try:
            os.remove(os.path.join(folder, item["name"]))
        except OSError:
            pass


def collect(folder, order, desc=False, seed=None):
    """Every image in the folder, in the order it will be numbered."""
    entries = []
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if not os.path.isfile(path) or not name.lower().endswith(IMAGE_EXTENSIONS):
            continue
        # A staging name only exists mid run, or after a hard kill during one.
        # Numbering it as though it were content would bake the accident in.
        if name.startswith(HALFWAY) or name.startswith(INSERTED):
            continue
        stat = os.stat(path)
        # st_ctime is the creation time on Windows, the one Explorer shows as
        # Date created. It is when the file arrived on this machine, so a folder
        # that was copied carries the time of the copy rather than the time the
        # picture was taken. --by modified is usually closer to that.
        entries.append({"name": name, "created": stat.st_ctime,
                        "modified": stat.st_mtime, "size": stat.st_size,
                        "type": os.path.splitext(name)[1].lower(),
                        "key": natural_key(name)})

    if order == "random":
        # Seeded so a shuffle can be repeated. Without a seed the run picks one
        # and prints it, because otherwise an order you liked is unrepeatable.
        random.Random(seed).shuffle(entries)
        return entries

    if order == "name":
        entries.sort(key=lambda entry: entry["key"], reverse=desc)
        return entries

    # Copying a folder stamps every file inside it with the same time, often to
    # the second, so the filename decides the order within a tie. Without that
    # the result would depend on the order the folder happens to list. The tie
    # break stays A to Z either way, so reversing the order does not scramble
    # the files that share a timestamp.
    entries.sort(key=lambda entry: entry["key"])
    entries.sort(key=lambda entry: entry[order], reverse=desc)
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
    """The most recent record that has not been undone already.

    Ordered by when the file was written, not by its name. Two runs in the same
    second produce 20260829-075435.json and 20260829-075435-2.json, and sorting
    those as text puts the second one first, because a hyphen sorts before a
    dot. That handed --undo the older record, which it then applied to a folder
    that had moved on.
    """
    if not os.path.isdir(LOGS):
        return None
    names = [name for name in os.listdir(LOGS)
             if name.endswith(".json") and not name.endswith(".undone.json")]
    if not names:
        return None
    paths = [os.path.join(LOGS, name) for name in names]
    return max(paths, key=lambda path: (os.path.getmtime(path), path))


def undo(wanted=None, force=False):
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

    # Check the whole record against the folder before touching any of it. A
    # half applied undo is worse than none: it leaves the folder in a state that
    # matches neither the record nor what the user had, and the second half of
    # the record can no longer be trusted to fix it.
    # Only the names the folder is meant to be resting on. Every rename went
    # through a halfway name that is not supposed to exist once the run is over,
    # so checking for those would report every healthy record as broken.
    missing = [destination for _, destination in moves
               if not destination.startswith(HALFWAY)
               and not os.path.exists(os.path.join(folder, destination))]
    if missing and not force:
        print("  This record does not match the folder any more.")
        print("  %d of %d files it expects are not there, starting with %s."
              % (len(missing), len(moves), missing[0]))
        print()
        print("  Nothing was changed. The folder was probably renamed again since,")
        print("  or these files were moved by hand. Undo the most recent run first,")
        print("  or name the record you want:")
        print("    Rename Images.bat --undo temp\\renames\\<record>.json")
        print("  Add --yes to undo as much of this record as still applies.")
        print()
        return 2

    # Backwards, because the forward moves went through temporary names and the
    # last one out of a name has to be the first one back into it.
    restored = 0
    removed = 0
    for source, destination in reversed(moves):
        current = os.path.join(folder, destination)
        original = os.path.join(folder, source)
        if not os.path.exists(current):
            print("  [!] %s is no longer there, skipped" % destination)
            continue
        # An image this run copied in has no earlier name to go back to. Putting
        # the folder back as it was means removing the copy.
        if source.startswith(INSERTED):
            os.remove(current)
            removed += 1
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
    wanted = sum(1 for source, _ in moves
                 if not source.startswith(HALFWAY) and not source.startswith(INSERTED))
    print("  put back %d of %d names" % (restored, wanted))
    if removed:
        print("  removed %d image(s) that run had inserted" % removed)
    print()
    return 0 if (restored or removed) else 1


def report(folder, pairs, order, entries=None):
    changing = [(old, new) for old, new in pairs if old != new]
    labels, added = {}, {}
    for index, entry in enumerate(entries or []):
        labels[entry["name"]] = entry.get("label", entry["name"])
        if entry.get("inserted"):
            added[entry["name"]] = pairs[index][1]

    print("  folder    : %s" % _shown(folder))
    print("  images    : %d" % len(pairs))
    print("  order     : %s" % order)
    if added:
        print()
        print("  inserting :")
        # Always listed in full, never clipped to PREVIEW. An image going in at
        # 150 would otherwise scroll off and the user would approve it unseen.
        for name, number in added.items():
            print("    %-40s ->  %s" % (_clipped(labels.get(name, name), 40), number))
    print()
    for old, new in changing[:PREVIEW]:
        print("    %-40s ->  %s" % (_clipped(labels.get(old, old), 40), new))
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
        return undo(args.undo or None, force=args.yes)

    folder = os.path.abspath(args.folder)
    # Made rather than reported missing, for the same reason the step files make
    # it: a folder the instructions point at should be there to be opened.
    os.makedirs(folder, exist_ok=True)

    # A shuffle nobody can repeat is a shuffle you cannot go back to, so when no
    # seed was given one is chosen here and reported with the result.
    seed = args.seed
    if args.by == "random" and seed is None:
        seed = random.randrange(1, 1000000)

    entries = collect(folder, args.by, args.desc, seed)

    inserts, positions = args.insert or [], args.at or []
    order, desc = args.by, args.desc
    if not inserts and not args.dry_run and not args.yes and _can_prompt():
        inserts, positions, order, desc = ask_what_to_do(folder, len(entries), order, desc)
        if (order, desc) != (args.by, args.desc):
            if order == "random" and args.seed is None:
                seed = random.randrange(1, 1000000)
            entries = collect(folder, order, desc, seed)
    if len(inserts) != len(positions):
        print()
        print("  --insert and --at come in pairs, one --at for each --insert.")
        print("  Given %d image(s) and %d position(s)." % (len(inserts), len(positions)))
        print()
        return 2

    if not entries and not inserts:
        explain_setup(folder)
        return 2

    sources = []
    for given in inserts:
        path, problem = find_source(folder, given)
        if problem:
            print()
            print("  %s" % problem)
            print()
            return 2
        sources.append(path)

    staged = stage_inserts(folder, sources) if sources else []
    if staged:
        entries = place(entries, staged, positions)

    pairs = plan(entries, max(1, args.digits), args.start)
    changing = report(folder, pairs, order_label(order, desc, seed), entries)

    if not changing:
        discard_staged(folder, staged)
        print("  Already numbered in that order. Nothing to do.")
        print()
        return 0

    if args.dry_run:
        discard_staged(folder, staged)
        print("  Nothing was renamed, this was --dry-run.")
        print()
        return 0

    if not args.yes:
        if not _can_prompt():
            discard_staged(folder, staged)
            print("  Add --yes to rename without a question to answer.")
            print()
            return 2
        if not _confirm("  Rename %d files?" % len(changing), default_yes=True):
            discard_staged(folder, staged)
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
    record = write_log(folder, trail) if trail else None
    if record:
        _undo_hint(record)
    print()

    # Offered here, while the result is still on screen and the record is the
    # newest one, so changing your mind costs one keypress instead of a flag.
    # Enter leaves it alone, because that is what almost everyone wants.
    if record and not args.yes and _can_prompt():
        if _confirm("  Undo it and put the old names back?"):
            print()
            return undo(record)
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
