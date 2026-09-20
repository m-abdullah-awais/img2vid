"""Every endpoint in the contract, and the small ones that need no module of their own.

A route is a method and a pattern of path segments. `{name}` captures one
segment, already URL decoded, so an encoded slash stays inside the segment and
the name check refuses it. HEAD is answered by the GET route for the same path.
"""

from . import VERSION, arrange, files, preview, projects, render_job, snapshot, system, \
    thumbs, transcribe_job, trash, videos
from .httpio import ApiError, invalid, not_found, send_json


def _etag_matches(header, version):
    if not header:
        return False
    for candidate in header.split(","):
        value = candidate.strip()
        if value == "*":
            return True
        if value.startswith("W/"):
            value = value[2:]
        if value.strip('"') == version:
            return True
    return False


# --------------------------------------------------------------------------
# Health and projects
# --------------------------------------------------------------------------

def health(app, request):
    return 200, {"ok": True, "app": "img2vid", "version": VERSION}


def list_projects(app, request):
    summaries = []
    for project_id in projects.ids(app):
        try:
            summaries.append(snapshot.summary(app, project_id))
        except ApiError:
            continue
    summaries.sort(key=lambda item: item["updatedAt"], reverse=True)
    return 200, {"projects": summaries}


def create_project(app, request):
    project = projects.create(app, request.json().get("name"))
    return 201, {"project": snapshot.project(app, project["id"])[1]}


def get_project(app, request):
    version, data = snapshot.project(app, request.params["id"])
    etag = '"%s"' % version
    headers = [("ETag", etag)]
    if _etag_matches(request.headers.get("If-None-Match"), version):
        from .httpio import respond  # noqa: PLC0415
        respond(request.handler, 304, headers + [("Cache-Control", "no-cache")])
        return None
    send_json(request.handler, 200, data, headers, head=request.method == "HEAD")
    return None


def patch_project(app, request):
    """Rename a project, change its build settings, or both.

    The settings are also saved by a build, but the captions toggle has to
    outlive the page without one, so that turning captions on and coming back
    tomorrow finds them still on.
    """
    project_id = request.params["id"]
    stored = projects.load(app, project_id)
    body = request.json()
    if "name" not in body and "settings" not in body:
        raise invalid("Send a new name or new settings.", {"field": "name"})
    changes = {}
    if "name" in body:
        changes["name"] = projects.check_name(body["name"])
    if "settings" in body:
        if not isinstance(body["settings"], dict):
            raise invalid("settings must be an object.", {"field": "settings"})
        changes["settings"] = render_job.parse_settings(body["settings"], stored["settings"])
    projects.update(app, project_id, **changes)
    return 200, {"project": snapshot.project(app, project_id)[1]}


def delete_project(app, request):
    project_id = request.params["id"]
    project = projects.load(app, project_id)
    job = app.jobs.running()
    if job is not None and job.project_id == project_id:
        from .jobs import busy  # noqa: PLC0415
        raise busy(job)
    with app.locks.project(project_id):
        job = app.jobs.running()
        if job is not None and job.project_id == project_id:
            from .jobs import busy  # noqa: PLC0415
            raise busy(job)
        trash_id = trash.remove_project(app, project)
    snapshot.forget(app, project_id)
    return 200, {"trashId": trash_id}


def restore(app, request):
    kind, project_id = trash.restore(app, request.params["trashId"])
    project = snapshot.project(app, project_id)[1] if projects.exists(app, project_id) else None
    return 200, {"kind": kind, "projectId": project_id, "project": project}


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------

def job_status(app, request):
    raw = request.query.get("since") or "0"
    try:
        since = int(raw)
    except ValueError:
        raise invalid("since must be a number.")
    job = app.jobs.latest()
    events, last, truncated = app.jobs.events(since)
    return 200, {"job": job.to_dict() if job else None, "events": events, "next": last,
                 "truncated": truncated}


def job_cancel(app, request):
    request.json()
    job = app.jobs.cancel()
    return 200, {"job": job.to_dict() if job else None}


def job_list(app, request):
    return 200, {"jobs": [job.to_dict() for job in app.jobs.recent(20)]}


# --------------------------------------------------------------------------
# The table
# --------------------------------------------------------------------------

def _slot(function, kind):
    return lambda app, request: function(app, request, kind)


ROUTES = [
    ("GET", "api/health", health),
    ("GET", "api/projects", list_projects),
    ("POST", "api/projects", create_project),
    ("GET", "api/projects/{id}", get_project),
    ("PATCH", "api/projects/{id}", patch_project),
    ("DELETE", "api/projects/{id}", delete_project),
    ("POST", "api/trash/{trashId}/restore", restore),

    ("PUT", "api/projects/{id}/audio/{name}", _slot(files.put, "audio")),
    ("GET", "api/projects/{id}/audio/{name}", _slot(files.get, "audio")),
    ("DELETE", "api/projects/{id}/audio/{name}", _slot(files.delete, "audio")),
    ("GET", "api/projects/{id}/narration", preview.narration_route),
    ("GET", "api/projects/{id}/narration/peaks", preview.peaks_route),
    ("PUT", "api/projects/{id}/images/{name}", _slot(files.put, "images")),
    ("GET", "api/projects/{id}/images/{name}", _slot(files.get, "images")),
    ("DELETE", "api/projects/{id}/images/{name}", _slot(files.delete, "images")),
    ("GET", "api/projects/{id}/images/{name}/thumb", thumbs.route),
    ("PUT", "api/projects/{id}/lines/{line}/image", arrange.upload_to_line),
    ("GET", "api/projects/{id}/transcript/raw", files.get_raw),
    ("PUT", "api/projects/{id}/transcript/raw", files.put_raw),
    ("GET", "api/projects/{id}/transcript/download", files.download_transcript),
    ("PUT", "api/projects/{id}/transcript/{name}", files.put_transcript),
    ("DELETE", "api/projects/{id}/transcript", files.delete_transcript),

    ("POST", "api/projects/{id}/transcribe", transcribe_job.start),
    ("POST", "api/projects/{id}/render", render_job.start),
    ("POST", "api/system/check", system.check),
    ("POST", "api/system/model", system.model),
    ("GET", "api/job", job_status),
    ("POST", "api/job/cancel", job_cancel),
    ("GET", "api/jobs", job_list),

    ("GET", "api/projects/{id}/videos", videos.list_route),
    ("GET", "api/projects/{id}/videos/{name}", videos.get),
    ("DELETE", "api/projects/{id}/videos/{name}", videos.delete),

    ("POST", "api/projects/{id}/arrange/preview", arrange.preview),
    ("POST", "api/projects/{id}/arrange", arrange.apply),
    ("POST", "api/projects/{id}/rename/preview", arrange.rename_preview),
    ("POST", "api/projects/{id}/rename/apply", arrange.rename_apply),
    ("POST", "api/projects/{id}/undo", arrange.undo),

    ("GET", "api/system", system.info_route),
]

_TABLE = [(method, pattern.split("/"), handler) for method, pattern, handler in ROUTES]


def match(method, segments):
    """(handler, params) for this request, or 404."""
    wanted = "GET" if method == "HEAD" else method
    for route_method, pattern, handler in _TABLE:
        if route_method != wanted or len(pattern) != len(segments):
            continue
        params = {}
        for expected, actual in zip(pattern, segments):
            if expected.startswith("{"):
                params[expected[1:-1]] = actual
            elif expected != actual:
                break
        else:
            return handler, params
    raise not_found("There is no %s %s endpoint." % (method, "/" + "/".join(segments)))
