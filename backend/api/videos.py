r"""Finished videos: listing, the meta file beside them, serving and removal.

    videos\2026-09-18_10-15-00.mp4
    videos\.meta.json      {name: {summary, createdAt, settings, jobId}}

The meta file only exists for videos this app built. A video imported from the
old output folder, or copied in by hand, lists with a null summary.
"""

import json
import os
import secrets

from . import projects, trash
from .httpio import api_url, iso, send_file

META = ".meta.json"


def folder(app, project_id):
    return projects.folder(app, project_id, "videos")


def read_meta(app, project_id):
    try:
        with open(os.path.join(folder(app, project_id), META), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_meta(app, project_id, meta):
    path = os.path.join(folder(app, project_id), META)
    if not meta:
        try:
            os.remove(path)
        except OSError:
            pass
        return
    temporary = "%s.%s.tmp" % (path, secrets.token_hex(3))
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2, ensure_ascii=False)
    os.replace(temporary, path)


def put_meta(app, project_id, name, entry):
    with app.locks.project(project_id):
        meta = read_meta(app, project_id)
        meta[name] = entry
        write_meta(app, project_id, meta)


def pop_meta(app, project_id, name):
    with app.locks.project(project_id):
        meta = read_meta(app, project_id)
        entry = meta.pop(name, None)
        write_meta(app, project_id, meta)
        return entry


def free_name(where, stem):
    """stem.mp4, or stem-2.mp4 and so on when two builds finish in the same second."""
    name = stem + ".mp4"
    counter = 2
    while os.path.exists(os.path.join(where, name)):
        name = "%s-%d.mp4" % (stem, counter)
        counter += 1
    return name


def ref(app, project_id, path, info, entry, inputs_ns):
    name = os.path.basename(path)
    seconds = app.media.duration(path)
    url = api_url("projects", project_id, "videos", name)
    return {
        "name": name,
        "bytes": info.st_size,
        "seconds": round(seconds, 3) if seconds is not None else 0,
        "createdAt": (entry or {}).get("createdAt") or iso(info.st_mtime),
        "url": url,
        "download": url + "?download=1",
        "outdated": inputs_ns > info.st_mtime_ns,
        "summary": (entry or {}).get("summary"),
    }


def listing(app, project_id, inputs_ns=0):
    """Every video, newest first."""
    where = folder(app, project_id)
    meta = read_meta(app, project_id)
    found = []
    try:
        names = os.listdir(where)
    except OSError:
        return []
    for name in names:
        path = os.path.join(where, name)
        if not name.lower().endswith(".mp4"):
            continue
        try:
            info = os.stat(path)
        except OSError:
            continue
        if not os.path.isfile(path):
            continue
        found.append((info.st_mtime_ns, name, path, info))
    found.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [ref(app, project_id, path, info, meta.get(name), inputs_ns)
            for _, name, path, info in found]


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

def list_route(app, request):
    from . import snapshot  # noqa: PLC0415 - snapshot imports this module

    _, snap = snapshot.project(app, request.params["id"])
    return 200, {"videos": snap["videos"]}


def get(app, request):
    from . import files  # noqa: PLC0415

    project_id = request.params["id"]
    projects.load(app, project_id)
    _, actual, path = files.existing(app, project_id, "videos", request.params["name"])
    if not actual.lower().endswith(".mp4"):
        from .httpio import not_found  # noqa: PLC0415
        raise not_found("There is no video called %s." % request.params["name"])
    download = actual if request.flag("download") else None
    send_file(request.handler, path, "video/mp4", head=request.method == "HEAD",
              download=download)
    return None


def delete(app, request):
    from . import files, snapshot  # noqa: PLC0415

    project_id = request.params["id"]
    project = projects.load(app, project_id)
    with app.locks.project(project_id):
        _, actual, path = files.existing(app, project_id, "videos", request.params["name"])
        entry = read_meta(app, project_id).get(actual)
        extra = {"videoMeta": {actual: entry}} if entry else None
        trash_id = trash.remove_files(app, project, "video", [path], extra)
        if entry:
            pop_meta(app, project_id, actual)
    projects.touch(app, project_id)
    return 200, {"trashId": trash_id, "project": snapshot.project(app, project_id)[1]}
