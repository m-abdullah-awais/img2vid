r"""Projects on disk: ids, folders and project.json.

    projects\<id>\project.json   {id, name, createdAt, updatedAt, settings}
    projects\<id>\audio\         narration, joined in natural filename order
    projects\<id>\images\        one image per transcript line
    projects\<id>\transcript\    the transcript, .srt preferred over .vtt over .txt
    projects\<id>\videos\        finished videos, plus .meta.json

An id is a lowercase ASCII slug of the name, a hyphen and four hex characters,
so it reads well in a folder listing and two projects of the same name differ.
"""

import json
import os
import re
import secrets
import time
import unicodedata

from .httpio import ApiError, invalid, iso, not_found

FOLDERS = ("audio", "images", "transcript", "videos")

DEFAULT_SETTINGS = {
    "fps": 30, "size": "1920x1080", "fit": "contain", "background": "black",
    # Off until asked for, so a plain build stays exactly as fast as it was.
    "captions": {"on": False, "place": "bottom", "distance": 8, "size": "medium",
                 "look": "outline"},
}

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")

NAME_LIMIT = 100


def slug(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return text[:40].strip("-") or "project"


def download_stem(project):
    """The project's name as it can be saved on Windows, for a download's name.

    `slug` is for folder ids, so it lowercases and replaces every space with a
    hyphen. A file the user is about to keep should carry the name they gave the
    project, so this only removes what Windows refuses: the nine forbidden
    characters, control characters, and trailing dots or spaces.
    """
    name = "".join(" " if ord(ch) < 32 else ch for ch in project.get("name") or "")
    name = " ".join(re.sub(r'[\\/:*?"<>|]+', " ", name).split())[:60].rstrip(" .")
    return name or project["id"]


def check_name(name):
    if not isinstance(name, str):
        raise invalid("Give the project a name.")
    name = " ".join(name.split())
    if not name:
        raise invalid("Give the project a name.")
    if len(name) > NAME_LIMIT:
        raise invalid("Keep the project name under %d characters." % NAME_LIMIT)
    return name


def check_id(project_id):
    if not isinstance(project_id, str) or not _ID.match(project_id):
        raise not_found("There is no project with that id.")
    return project_id


def folder(app, project_id, kind=None):
    base = os.path.join(app.config.projects, check_id(project_id))
    return os.path.join(base, kind) if kind else base


def project_file(app, project_id):
    return os.path.join(folder(app, project_id), "project.json")


def exists(app, project_id):
    try:
        return os.path.isfile(project_file(app, project_id))
    except ApiError:
        return False


def ids(app):
    try:
        names = os.listdir(app.config.projects)
    except OSError:
        return []
    return [name for name in names if _ID.match(name)
            and os.path.isfile(os.path.join(app.config.projects, name, "project.json"))]


def load(app, project_id):
    path = project_file(app, project_id)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        raise not_found("There is no project with that id. It may have been deleted.")
    except (OSError, ValueError) as error:
        raise ApiError(500, "internal", "project.json for %s cannot be read: %s"
                       % (project_id, error))
    data["id"] = project_id
    data.setdefault("name", project_id)
    data.setdefault("createdAt", iso(os.path.getmtime(path)))
    data.setdefault("updatedAt", data["createdAt"])
    data["settings"] = settings(data)
    # A folder removed by hand comes back empty rather than failing every call.
    for kind in FOLDERS:
        os.makedirs(folder(app, project_id, kind), exist_ok=True)
    return data


def settings(project):
    merged = dict(DEFAULT_SETTINGS)
    stored = project.get("settings") or {}
    merged.update({key: stored[key] for key in DEFAULT_SETTINGS if key in stored})
    # Captions are a group of their own, so an older project.json written before
    # they existed, or one holding half of them, still comes back complete.
    captions = dict(DEFAULT_SETTINGS["captions"])
    if isinstance(stored.get("captions"), dict):
        captions.update({key: stored["captions"][key] for key in captions
                         if key in stored["captions"]})
    merged["captions"] = captions
    return merged


def save(app, project):
    path = project_file(app, project["id"])
    data = {key: project[key] for key in ("id", "name", "createdAt", "updatedAt", "settings")}
    temporary = "%s.%s.tmp" % (path, secrets.token_hex(3))
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    os.replace(temporary, path)
    return data


def new_id(app, name):
    stem = slug(name)
    while True:
        candidate = "%s-%s" % (stem, secrets.token_hex(2))
        if not os.path.exists(os.path.join(app.config.projects, candidate)):
            return candidate


def create(app, name):
    name = check_name(name)
    project_id = new_id(app, name)
    for kind in FOLDERS:
        os.makedirs(folder(app, project_id, kind), exist_ok=True)
    stamp = iso(time.time())
    project = {"id": project_id, "name": name, "createdAt": stamp, "updatedAt": stamp,
               "settings": dict(DEFAULT_SETTINGS)}
    with app.locks.project(project_id):
        save(app, project)
    return project


def update(app, project_id, **changes):
    """Change fields of project.json and bump updatedAt, under the project lock."""
    with app.locks.project(project_id):
        project = load(app, project_id)
        project.update(changes)
        project["updatedAt"] = iso(time.time())
        save(app, project)
        return project


def touch(app, project_id):
    """Record that something in the project changed."""
    try:
        return update(app, project_id)
    except ApiError:
        return None
