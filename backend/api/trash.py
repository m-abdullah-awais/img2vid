r"""Removed and replaced things, kept for seven days so they can be put back.

    trash\<trashId>\meta.json          what it was and where it came from
    trash\<trashId>\files\<kind>\...   the files, under their project relative path
    trash\<trashId>\project\           a whole project

Everything moves with os.replace, which is a rename on the same volume, so
trashing a 2 GB narration costs nothing and restoring it puts back the exact
file, timestamps included.
"""

import json
import os
import re
import secrets
import shutil
import time

from . import projects
from .httpio import ApiError, in_use, invalid, iso, not_found, parse_iso

PURGE_AFTER = 7 * 24 * 3600

_ID = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")

# Which job lock guards the folder each kind of entry goes back into.
LOCK_PART = {"audio": "audio", "image": "images", "transcript": "transcript"}


def _new_id():
    return "%s-%s" % (time.strftime("%Y%m%d-%H%M%S", time.gmtime()), secrets.token_hex(2))


def _entry(app, trash_id):
    if not isinstance(trash_id, str) or not _ID.match(trash_id):
        raise not_found("Nothing in the trash has that id.")
    return os.path.join(app.config.trash, trash_id)


def _write_meta(folder, meta):
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2, ensure_ascii=False)


def read_meta(app, trash_id):
    folder = _entry(app, trash_id)
    try:
        with open(os.path.join(folder, "meta.json"), "r", encoding="utf-8") as handle:
            return folder, json.load(handle)
    except (OSError, ValueError):
        raise not_found("Nothing in the trash has that id. It may have been restored or purged.")


def remove_files(app, project, kind, paths, extra=None):
    """Move files out of a project into one trash entry and return its id.

    All or nothing: if Windows refuses one of the moves, the ones already made
    are put back and the call fails with `in_use`.
    """
    base = projects.folder(app, project["id"])
    trash_id = _new_id()
    entry = os.path.join(app.config.trash, trash_id)
    while os.path.exists(entry):
        trash_id = _new_id()
        entry = os.path.join(app.config.trash, trash_id)
    os.makedirs(entry)
    items, moved = [], []
    try:
        for path in paths:
            relative = os.path.relpath(path, base)
            if relative.startswith(".."):
                raise ValueError("%s is not inside the project" % path)
            stored = os.path.join("files", relative)
            target = os.path.join(entry, stored)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.replace(path, target)
            moved.append((path, target))
            items.append({"path": relative.replace(os.sep, "/"),
                          "stored": stored.replace(os.sep, "/")})
    except OSError as error:
        for original, target in reversed(moved):
            try:
                os.replace(target, original)
            except OSError:
                pass
        shutil.rmtree(entry, ignore_errors=True)
        if isinstance(error, PermissionError):
            raise in_use()
        raise
    _write_meta(entry, {"id": trash_id, "kind": kind, "projectId": project["id"],
                        "projectName": project.get("name"), "removedAt": iso(time.time()),
                        "items": items, "extra": extra or {}})
    return trash_id


def remove_project(app, project):
    base = projects.folder(app, project["id"])
    trash_id = _new_id()
    entry = os.path.join(app.config.trash, trash_id)
    os.makedirs(entry)
    try:
        os.replace(base, os.path.join(entry, "project"))
    except PermissionError:
        shutil.rmtree(entry, ignore_errors=True)
        raise in_use("Windows would not let the project be moved, usually because one of "
                     "its files is open, such as a video that is playing. Close it and "
                     "try again.")
    _write_meta(entry, {"id": trash_id, "kind": "project", "projectId": project["id"],
                        "projectName": project.get("name"), "removedAt": iso(time.time()),
                        "items": [], "extra": {}})
    return trash_id


def restore(app, trash_id, check_locks=True):
    """Put an entry back exactly where it came from. Returns (kind, project_id).

    Refuses with `exists` rather than overwrite anything that has since taken
    its place, and checks every destination before moving any of them.
    """
    from . import files, videos  # noqa: PLC0415 - they import this module too

    folder, meta = read_meta(app, trash_id)
    kind = meta.get("kind")
    project_id = meta.get("projectId")

    if kind == "project":
        destination = projects.folder(app, project_id)
        if os.path.exists(destination):
            raise ApiError(409, "exists", "That project is already back.", {"name": project_id})
        try:
            os.replace(os.path.join(folder, "project"), destination)
        except PermissionError:
            raise in_use()
        shutil.rmtree(folder, ignore_errors=True)
        return kind, project_id

    if not projects.exists(app, project_id):
        raise not_found("The project this came from is gone. Restore the project first.")
    if check_locks and kind in LOCK_PART:
        app.locks.check(project_id, LOCK_PART[kind])
    base = projects.folder(app, project_id)

    with app.locks.project(project_id):
        plan = []
        for item in meta.get("items", []):
            relative = item["path"].replace("/", os.sep)
            destination = os.path.normpath(os.path.join(base, relative))
            if os.path.dirname(os.path.dirname(destination)) != os.path.normpath(base):
                raise invalid("That trash entry points outside its project.")
            parent = os.path.dirname(destination)
            os.makedirs(parent, exist_ok=True)
            taken = files.find(parent, os.path.basename(destination))
            if taken:
                raise ApiError(409, "exists",
                               "%s is already there. Remove it first, then restore this."
                               % taken, {"name": taken})
            plan.append((os.path.join(folder, item["stored"].replace("/", os.sep)), destination))
        done = []
        try:
            for source, destination in plan:
                os.replace(source, destination)
                done.append((source, destination))
        except OSError as error:
            for source, destination in reversed(done):
                try:
                    os.replace(destination, source)
                except OSError:
                    pass
            if isinstance(error, PermissionError):
                raise in_use()
            raise
        for name, entry in (meta.get("extra") or {}).get("videoMeta", {}).items():
            videos.put_meta(app, project_id, name, entry)
    shutil.rmtree(folder, ignore_errors=True)
    projects.touch(app, project_id)
    if kind == "image":
        for _, destination in plan:
            app.thumbs.enqueue(destination)
    return kind, project_id


def discard(app, trash_id):
    """Delete an entry outright, for trash the API made and no longer needs."""
    try:
        shutil.rmtree(_entry(app, trash_id), ignore_errors=True)
    except ApiError:
        pass


def purge(app, now=None):
    """Delete entries older than seven days. Returns how many went."""
    now = now or time.time()
    removed = 0
    try:
        names = os.listdir(app.config.trash)
    except OSError:
        return 0
    for name in names:
        entry = os.path.join(app.config.trash, name)
        if not os.path.isdir(entry):
            continue
        when = None
        try:
            with open(os.path.join(entry, "meta.json"), "r", encoding="utf-8") as handle:
                when = parse_iso(json.load(handle).get("removedAt"))
        except (OSError, ValueError, AttributeError):
            pass
        if when is None:
            try:
                when = os.path.getmtime(entry)
            except OSError:
                continue
        if now - when > PURGE_AFTER:
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    return removed


def size(app):
    total = 0
    for folder, _, names in os.walk(app.config.trash):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(folder, name))
            except OSError:
                pass
    return total
