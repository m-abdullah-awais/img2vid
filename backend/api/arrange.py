"""Putting images on lines, renumbering the folder, and undoing either.

Every change is a set of renames carried out by rename_images.apply_plan, which
goes through temporary names in two passes so a swap or a shift can never
collide with itself, and is recorded with rename_images.write_log. The record's
file name is the undoId, and undo replays it backwards with
rename_images.replay after checking with read_record that it still matches.

The rules, from the contract:

    place    the image goes onto the line. An empty line simply receives it,
             an occupied line swaps the two images, nothing else moves
    insert   the image goes onto the line and the images from there down move
             one line later each, stopping at the first empty line at or after
             it, which absorbs the shift. The image is lifted out of its own
             line first, so that line counts as empty. No empty line, no insert
    naming   the line's number padded to the folder's width, then whatever the
             name carried after its own leading number, then its extension:
             "004. two men.jpg" on line 7 is "007. two men.jpg"

A folder paired by position is numbered in its current on screen order first,
as part of the same change, so one undo puts back both.
"""

import hashlib
import json
import os
import re
import threading

import rename_images
from i2v import render

from . import files, projects, snapshot, trash
from .httpio import ApiError, in_use, invalid, not_found

_LEADING = re.compile(r"^\d+")
_UNDO_ID = re.compile(r"^\d{8}-\d{6}(?:-\d+)?\.json$")

# write_log keeps its records in the module global rename_images.LOGS. It is
# pointed at this server's storage for each write, under a lock, so two servers
# in one process (the tests run a second one) each keep their own records.
_LOGS_LOCK = threading.Lock()


def write_log(app, folder, trail):
    """rename_images.write_log, into this server's storage, under a name undo can retire.

    write_log only steps around records that still end in .json. Once one is
    undone it becomes .undone.json, and a second change in the same second then
    gets the freed name, so undoing that one would collide with the first
    retired record. Such a record is moved to a suffix nothing has used.
    """
    with _LOGS_LOCK:
        rename_images.LOGS = app.config.renames
        path = rename_images.write_log(folder, trail)
        stem = path[:-len(".json")]
        if os.path.exists(stem + ".undone.json"):
            stamp = os.path.join(os.path.dirname(path), os.path.basename(stem)[:15])
            counter = 2
            while os.path.exists("%s-%d.json" % (stamp, counter)) or \
                    os.path.exists("%s-%d.undone.json" % (stamp, counter)):
                counter += 1
            moved = "%s-%d.json" % (stamp, counter)
            os.replace(path, moved)
            path = moved
        return path


def compose(name, number, width):
    """The naming rule: number, then what followed the old leading number, then the extension."""
    stem, extension = os.path.splitext(name)
    match = _LEADING.match(stem)
    rest = stem[match.end():] if match else ""
    return "%0*d%s%s" % (width, number, rest, extension)


class Folder:
    """The images folder as numbers: what each image is numbered now."""

    def __init__(self, app, project_id, facts):
        self.path = projects.folder(app, project_id, "images")
        self.count = len(facts.lines)
        report = facts.report
        self.names = [os.path.basename(path) for path in facts.images]
        self.numbers_folder = report["mode"] == "positional"
        self.reason = report["reason"]
        self.base = snapshot.base_of(report)
        self.width = snapshot.width(facts)
        if report["mode"] == "numbered":
            self.number = {name: int(_LEADING.match(name).group()) for name in self.names}
        else:
            # Numbered in natural filename order, which is the order the render
            # pairs them in and the order the screen shows them in.
            self.number = {name: self.base + index for index, name in enumerate(self.names)}
        _, self.line_before = snapshot.placement(facts)

    def target(self, line):
        return line - 1 + self.base

    def line_of(self, number):
        line = number - self.base + 1
        return line if 1 <= line <= self.count else None

    def holders(self, number, excluding=None):
        return [name for name in self.names
                if self.number[name] == number and name != excluding]

    def first_gap(self, number, excluding=None):
        """The first number at or after this one that no image holds, within the lines."""
        last = self.count - 1 + self.base
        for candidate in range(number, last + 1):
            if not self.holders(candidate, excluding):
                return candidate
        return None

    def renames(self, new):
        """[(old, new)] for every image whose name changes under these numbers."""
        pairs = []
        for name in self.names:
            if self.numbers_folder or new[name] != self.number[name]:
                wanted = compose(name, new[name], self.width)
                if wanted != name:
                    pairs.append((name, wanted))
        return pairs

    def clash(self, pairs, extra=()):
        """A name two images would both end up with, or None."""
        renamed = dict(pairs)
        finals = [renamed.get(name, name) for name in self.names] + list(extra)
        seen = set()
        for name in finals:
            key = name.casefold()
            if key in seen:
                return name
            seen.add(key)
        return None


def _range_words(first, last):
    return "line %d" % first if first == last else "lines %d to %d" % (first, last)


def plan(folder, op, image, line):
    """What an arrangement would do. Returns a dict with allowed, reason, summary, pairs, new."""
    target = folder.target(line)
    own = folder.number[image]
    own_line = folder.line_before.get(image)
    new = dict(folder.number)
    words = []
    if folder.numbers_folder and folder.names:
        words.append("Number the %d images %s to %s in their current order first"
                     % (len(folder.names), "%0*d" % (folder.width, folder.base),
                        "%0*d" % (folder.width, folder.base + len(folder.names) - 1)))

    if op == "place":
        occupants = folder.holders(target, excluding=image)
        new[image] = target
        for name in occupants:
            new[name] = own
        if own == target:
            words.append("%s is already on line %d" % (image, line))
        elif not occupants:
            words.append("Put %s on line %d" % (image, line)
                         + (", leaving line %d empty" % own_line if own_line else ""))
        else:
            where = ("line %d" % own_line) if own_line else "its place, off the lines"
            words.append("Swap %s and %s: %s goes to line %d and %s to %s"
                         % (image, occupants[0], image, line, occupants[0], where))
    else:
        gap = folder.first_gap(target, excluding=image)
        if gap is None:
            reason = ("Every line from %d to the last line, %d, has an image, so there is no "
                      "empty line to take up the shift. Remove an image, or place this one "
                      "instead of inserting it." % (line, folder.count))
            return {"allowed": False, "reason": reason, "code": "no_gap",
                    "summary": "Cannot insert %s at line %d" % (image, line),
                    "pairs": [], "new": new}
        for number in range(target, gap):
            for name in folder.holders(number, excluding=image):
                new[name] = number + 1
        new[image] = target
        if gap == target:
            words.append("Put %s on line %d, which is empty" % (image, line)
                         if own != target else "%s is already on line %d" % (image, line))
        else:
            words.append("Insert %s at line %d and move %s down one line, into empty line %d"
                         % (image, line, _range_words(line, folder.line_of(gap - 1) or line),
                            folder.line_of(gap) or gap))

    pairs = folder.renames(new)
    taken = folder.clash(pairs)
    if taken:
        return {"allowed": False, "code": "name_clash",
                "reason": "Two images would both be called %s. Rename one of them first." % taken,
                "summary": "Cannot arrange %s" % image, "pairs": [], "new": new}
    return {"allowed": True, "reason": None, "code": None,
            "summary": ". ".join(words) + ".", "pairs": pairs, "new": new}


def changes(folder, result):
    renamed = dict(result["pairs"])
    return [{"from": name, "to": renamed[name], "lineBefore": folder.line_before.get(name),
             "lineAfter": folder.line_of(result["new"][name])}
            for name in folder.names if name in renamed]


def _arrange_request(app, request):
    project_id = request.params["id"]
    projects.load(app, project_id)
    body = request.json()
    op = body.get("op")
    if op not in ("place", "insert"):
        raise invalid("op must be place or insert.", {"field": "op"})
    image = body.get("image")
    files.check_name(image)
    line = body.get("line")
    if isinstance(line, bool) or not isinstance(line, int):
        raise invalid("line must be a line number.", {"field": "line"})
    return project_id, op, image, line


def _folder_for(app, project_id, image, line):
    facts = snapshot.gather(app, project_id)
    if not facts.lines:
        raise ApiError(409, "positional", "There is no transcript yet, so there are no lines "
                       "to put images on.", {"reason": {"kind": "no_lines", "name": None,
                                                        "number": None}})
    if not 1 <= line <= len(facts.lines):
        raise invalid("line must be from 1 to %d." % len(facts.lines), {"field": "line"})
    folder = Folder(app, project_id, facts)
    actual = next((name for name in folder.names if name.casefold() == image.casefold()), None)
    if actual is None:
        raise not_found("There is no image called %s in this project." % image)
    return folder, actual


def preview(app, request):
    project_id, op, image, line = _arrange_request(app, request)
    folder, image = _folder_for(app, project_id, image, line)
    result = plan(folder, op, image, line)
    return 200, {"allowed": result["allowed"], "reason": result["reason"],
                 "summary": result["summary"], "numbersFolder": folder.numbers_folder,
                 "changes": changes(folder, result) if result["allowed"] else []}


def apply(app, request):
    project_id, op, image, line = _arrange_request(app, request)
    app.locks.check(project_id, "images")
    with app.locks.project(project_id):
        app.locks.check(project_id, "images")
        folder, image = _folder_for(app, project_id, image, line)
        result = plan(folder, op, image, line)
        if not result["allowed"]:
            raise ApiError(422, "blocked", result["reason"],
                           {"blockers": [{"code": result["code"], "message": result["reason"]}]})
        undo_id = execute(app, project_id, folder.path, result["pairs"])
        listed = changes(folder, result)
    projects.touch(app, project_id)
    return 200, {"undoId": undo_id, "summary": result["summary"], "changes": listed,
                 "project": snapshot.project(app, project_id)[1]}


# --------------------------------------------------------------------------
# Carrying out a plan
# --------------------------------------------------------------------------

def rollback(folder, trail):
    """Reverse the moves apply_plan made before it failed. True if all went back."""
    ok = True
    for source, destination in reversed(trail):
        try:
            os.rename(os.path.join(folder, destination), os.path.join(folder, source))
        except OSError:
            ok = False
    return ok


def execute(app, project_id, folder, pairs, before=None):
    """Apply renames with the images fenced off from readers. Returns the undoId or None.

    `before` runs inside the fence first, for a caller that has to put a file
    in place as part of the same change.
    """
    if not pairs and before is None:
        return None
    trail = []
    with app.locks.images(project_id).exclusive():
        if before is not None:
            before()
        try:
            rename_images.apply_plan(folder, pairs, trail)
        except OSError as error:
            if rollback(folder, trail):
                raise in_use() if isinstance(error, PermissionError) else error
            record = write_log(app, folder, trail)
            raise ApiError(409, "in_use", "Windows stopped the renaming part way and not every "
                           "name could be put back. Undo it to restore the rest.",
                           {"undoId": os.path.basename(record)})
    if not trail:
        return None
    return os.path.basename(write_log(app, folder, trail))


# --------------------------------------------------------------------------
# An upload straight onto a line
# --------------------------------------------------------------------------

def upload_to_line(app, request):
    """PUT /lines/{line}/image?name={original}[&insert=1]"""
    project_id = request.params["id"]
    project = projects.load(app, project_id)
    try:
        line = int(request.params["line"])
    except ValueError:
        raise invalid("The line must be a number.")
    original = files.check_name(request.query.get("name") or "")
    files.check_extension("images", original)
    files.check_size("images", request.content_length())
    insert = request.flag("insert")
    _line_folder(app, project_id, line)
    app.locks.check(project_id, "images")

    part = files.receive_upload(app, request, "images")
    try:
        with app.locks.project(project_id):
            app.locks.check(project_id, "images")
            folder = _line_folder(app, project_id, line)
            target = folder.target(line)
            saved = compose(original, target, folder.width)
            files.check_name(saved)
            trash_id = undo_id = None
            if not insert:
                occupants = folder.holders(target)
                others = [name for name in folder.names if name not in occupants]
                if saved.casefold() in {name.casefold() for name in others}:
                    raise ApiError(409, "exists", "%s is already in the folder." % saved,
                                   {"name": saved})
                with app.locks.images(project_id).exclusive():
                    if occupants:
                        trash_id = trash.remove_files(
                            app, project, "image",
                            [files.inside(folder.path, name) for name in occupants])
                    os.replace(part, files.inside(folder.path, saved))
            else:
                gap = folder.first_gap(target)
                if gap is None:
                    reason = ("Every line from %d to the last line, %d, has an image, so there "
                              "is no empty line to take up the shift. Save it onto the line "
                              "instead, which replaces the image there." % (line, folder.count))
                    raise ApiError(422, "blocked", reason,
                                   {"blockers": [{"code": "no_gap", "message": reason}]})
                new = dict(folder.number)
                for number in range(target, gap):
                    for name in folder.holders(number):
                        new[name] = number + 1
                pairs = folder.renames(new)
                staged = _staged_name(folder.path, os.path.splitext(original)[1])
                pairs.append((staged, saved))
                taken = folder.clash(pairs[:-1], extra=[saved])
                if taken:
                    raise ApiError(409, "exists", "Two images would both be called %s." % taken,
                                   {"name": taken})

                def put_in_place():
                    os.replace(part, os.path.join(folder.path, staged))

                try:
                    undo_id = execute(app, project_id, folder.path, pairs, before=put_in_place)
                except Exception:
                    files.discard(os.path.join(folder.path, staged))
                    raise
    finally:
        files.discard(part)
    projects.touch(app, project_id)
    app.thumbs.enqueue(os.path.join(projects.folder(app, project_id, "images"), saved))
    return 201, {"saved": saved, "trashId": trash_id, "undoId": undo_id,
                 "project": snapshot.project(app, project_id)[1]}


def _line_folder(app, project_id, line):
    facts = snapshot.gather(app, project_id)
    if not facts.lines:
        raise ApiError(409, "positional", "There is no transcript yet, so there are no lines "
                       "to put images on.", {"reason": {"kind": "no_lines", "name": None,
                                                        "number": None}})
    if not 1 <= line <= len(facts.lines):
        raise invalid("line must be from 1 to %d." % len(facts.lines), {"field": "line"})
    if facts.report["mode"] == "positional":
        raise ApiError(409, "positional",
                       "These images are paired by position, not by the number in their "
                       "names, so a line cannot be given its own image yet. Arrange or "
                       "renumber the images first.", {"reason": facts.report["reason"]})
    return Folder(app, project_id, facts)


def _staged_name(folder, extension):
    name = rename_images.INSERTED + "0" + extension
    counter = 2
    while os.path.exists(os.path.join(folder, name)):
        name = "%s0_%d%s" % (rename_images.INSERTED, counter, extension)
        counter += 1
    return name


# --------------------------------------------------------------------------
# Renumbering the whole folder
# --------------------------------------------------------------------------

def _int(body, key, default, low, high):
    value = body.get(key, default)
    if value is None:
        value = default
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise invalid("%s must be a whole number from %d to %d." % (key, low, high),
                      {"field": key})
    return value


def _lines_after(names, count):
    ordered = sorted(names, key=render.natural_key)
    report = render.placement_report([os.path.join("x", name) for name in ordered], count)
    if report["mode"] == "numbered":
        return {os.path.basename(path): index + 1 for index, path in enumerate(report["slots"])
                if path}
    if report["mode"] == "positional":
        return {name: index + 1 for index, name in enumerate(ordered[:count])}
    return {}


def rename_plan(app, project_id, body):
    by = body.get("by")
    if by is not None and by not in rename_images.ORDERS:
        raise invalid("by must be one of %s, or null." % ", ".join(rename_images.ORDERS),
                      {"field": "by"})
    desc = body.get("desc") is True
    seed = body.get("seed")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise invalid("seed must be a whole number.", {"field": "seed"})
    start = _int(body, "start", 1, 0, 100000)
    digits = _int(body, "digits", 3, 1, 8)

    facts = snapshot.gather(app, project_id)
    folder = projects.folder(app, project_id, "images")
    entries, order, desc, seed, kept = rename_images.resolve_order(folder, by, desc, seed)
    pairs = rename_images.plan(entries, digits, start)
    _, before = snapshot.placement(facts)
    after = _lines_after([new for _, new in pairs], len(facts.lines))
    rows = [{"from": old, "to": new, "lineBefore": before.get(old), "lineAfter": after.get(new)}
            for old, new in pairs]
    moved = [row for row in rows if row["lineBefore"] != row["lineAfter"]]
    shifted = None
    if moved:
        first = min(row["lineBefore"] if row["lineBefore"] is not None else row["lineAfter"]
                    for row in moved)
        shifted = {"count": len(moved), "first": first}
    plan_id = hashlib.sha1(json.dumps(pairs).encode("utf-8")).hexdigest()[:16]
    result = {
        "order": {"by": order, "desc": desc, "seed": seed,
                  "label": rename_images.order_label(order, desc),
                  "kept": {"wouldHave": kept[0], "first": kept[1]} if kept else None},
        "pairs": rows,
        "changing": sum(1 for old, new in pairs if old != new),
        "shifted": shifted,
        "planId": plan_id,
    }
    return result, pairs, folder


def rename_preview(app, request):
    project_id = request.params["id"]
    projects.load(app, project_id)
    result, _, _ = rename_plan(app, project_id, request.json())
    return 200, result


def rename_apply(app, request):
    project_id = request.params["id"]
    projects.load(app, project_id)
    body = request.json()
    wanted = body.get("planId")
    if not isinstance(wanted, str):
        raise invalid("Send the planId from the preview.", {"field": "planId"})
    app.locks.check(project_id, "images")
    with app.locks.project(project_id):
        app.locks.check(project_id, "images")
        result, pairs, folder = rename_plan(app, project_id, body)
        if result["planId"] != wanted:
            raise ApiError(409, "changed", "The images changed since that preview. Look at the "
                           "new preview before renaming.",
                           {"what": "plan", "planId": result["planId"]})
        undo_id = execute(app, project_id, folder, [(old, new) for old, new in pairs if old != new])
    projects.touch(app, project_id)
    return 200, {"undoId": undo_id, "project": snapshot.project(app, project_id)[1]}


# --------------------------------------------------------------------------
# Undo
# --------------------------------------------------------------------------

def _copied_in(moves):
    """Where each image an insert copied in ended up.

    Followed by replaying the moves in order, not by chasing names: the name
    the inserted image lands on was usually the source of an earlier move too.
    """
    finals = []
    for index, (source, _) in enumerate(moves):
        if source.startswith(rename_images.INSERTED):
            name = source
            for before, after in moves[index:]:
                if before == name:
                    name = after
            finals.append(name)
    return finals


def undo(app, request):
    project_id = request.params["id"]
    project = projects.load(app, project_id)
    undo_id = request.json().get("undoId")
    if not isinstance(undo_id, str) or not _UNDO_ID.match(undo_id):
        raise not_found("There is no change with that undoId to undo.")
    record = os.path.join(app.config.renames, undo_id)
    if not os.path.isfile(record):
        raise not_found("That change was already undone, or its record is gone.")
    images = projects.folder(app, project_id, "images")
    folder, _, _ = rename_images.read_record(record)
    if os.path.normcase(os.path.abspath(folder)) != os.path.normcase(os.path.abspath(images)):
        raise not_found("That change was made in a different project.")
    app.locks.check(project_id, "images")
    with app.locks.project(project_id):
        app.locks.check(project_id, "images")
        folder, moves, missing = rename_images.read_record(record)
        if missing:
            expected = [destination for _, destination in moves
                        if not destination.startswith(rename_images.HALFWAY)]
            raise ApiError(409, "record_mismatch",
                           "The images changed since then, so this cannot be undone safely. "
                           "%d of the %d files it expects are not there, starting with %s. "
                           "Nothing was changed." % (len(missing), len(expected), missing[0]),
                           {"missing": len(missing), "total": len(expected), "first": missing[0]})
        copied = [name for name in _copied_in(moves)
                  if os.path.isfile(os.path.join(folder, name))]
        with app.locks.images(project_id).exclusive():
            if copied:
                trash.remove_files(app, project, "image",
                                   [os.path.join(folder, name) for name in copied])
            try:
                rename_images.replay(record, folder, moves)
            except PermissionError:
                raise in_use()
    projects.touch(app, project_id)
    return 200, {"project": snapshot.project(app, project_id)[1]}
