r"""The files inside a project: naming rules, lookup, upload, download, removal.

Every name that arrives in a URL is a bare file name and is checked before it
is joined to anything. Lookups compare names case insensitively, the way
Windows does, and every resolved path is asserted to sit directly inside its
folder, so neither an encoded separator nor a junction can reach outside it.
"""

import hashlib
import os
import secrets
import time

import rename_images
from i2v import captions, paths

from . import projects, snapshot, trash
from .httpio import (ApiError, api_url, content_type, disposition, invalid, not_found,
                     receive, respond, send_file)

MB = 1024 * 1024

# Per slot: accepted extensions, size limit, the job lock that guards it, and
# the word used in messages.
SLOTS = {
    "audio": {"extensions": paths.AUDIO_EXTENSIONS, "limit": 2048 * MB, "part": "audio",
              "noun": "audio file", "trash": "audio"},
    "images": {"extensions": paths.IMAGE_EXTENSIONS, "limit": 50 * MB, "part": "images",
               "noun": "image", "trash": "image"},
    "transcript": {"extensions": paths.TRANSCRIPT_EXTENSIONS, "limit": 5 * MB,
                   "part": "transcript", "noun": "transcript", "trash": "transcript"},
}

LIMIT_WORDS = {"audio": "2 GB", "images": "50 MB", "transcript": "5 MB"}

_FORBIDDEN = set('<>:"/\\|?*')
_RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
             "COM¹", "COM²", "COM³", "LPT¹", "LPT²", "LPT³"}
_RESERVED.update("COM%d" % number for number in range(10))
_RESERVED.update("LPT%d" % number for number in range(10))

NAME_LIMIT = 180


# --------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------

def check_name(name):
    """A bare file name that is safe to create on Windows, or 400.

    Refuses the parent and current folder names, any separator or drive colon,
    control characters, the characters Windows forbids, reserved device names
    with or without an extension, and trailing dots or spaces, which Windows
    silently strips so the file would land under a different name.
    """
    if not isinstance(name, str) or not name:
        raise invalid("A file name is needed.")
    if len(name) > NAME_LIMIT:
        raise invalid("That file name is too long. Keep it under %d characters." % NAME_LIMIT)
    if name in (".", ".."):
        raise invalid("%r is not a file name." % name)
    for character in name:
        if character in _FORBIDDEN or ord(character) < 32 or ord(character) == 127:
            raise invalid("File names cannot contain %r." % character, {"name": name})
    if name != name.rstrip(" ."):
        raise invalid("File names cannot end with a dot or a space.", {"name": name})
    if name.split(".")[0].rstrip(" ").upper() in _RESERVED:
        raise invalid("%s is a name Windows reserves for a device. Rename the file." % name,
                      {"name": name})
    if name.startswith(rename_images.HALFWAY) or name.startswith(rename_images.INSERTED):
        raise invalid("Names starting with %s or %s are used while renaming."
                      % (rename_images.HALFWAY, rename_images.INSERTED), {"name": name})
    return name


def inside(folder, name):
    """The path of name in folder, asserted to resolve directly inside it."""
    base = os.path.realpath(folder)
    path = os.path.realpath(os.path.join(folder, name))
    if os.path.normcase(os.path.dirname(path)) != os.path.normcase(base):
        raise invalid("That name points outside its folder.", {"name": name})
    return os.path.join(folder, name)


def find(folder, name):
    """The name as it exists on disk, matched without regard to case, or None."""
    wanted = name.casefold()
    try:
        entries = os.listdir(folder)
    except OSError:
        return None
    for entry in entries:
        if entry.casefold() == wanted and os.path.isfile(os.path.join(folder, entry)):
            return entry
    return None


def existing(app, project_id, kind, name):
    """(folder, actual name, path) for a file that must already exist, or 404."""
    check_name(name)
    folder = projects.folder(app, project_id, kind)
    actual = find(folder, name)
    if actual is None:
        raise not_found("There is no %s called %s in this project."
                        % (SLOTS[kind]["noun"] if kind in SLOTS else "file", name))
    return folder, actual, inside(folder, actual)


def check_extension(kind, name):
    slot = SLOTS[kind]
    if not name.lower().endswith(slot["extensions"]):
        raise ApiError(415, "unsupported",
                       "%s is not a supported %s. Use one of: %s."
                       % (name, slot["noun"], ", ".join(slot["extensions"])),
                       {"name": name, "accepted": list(slot["extensions"])})


def check_size(kind, length):
    if length > SLOTS[kind]["limit"]:
        raise ApiError(413, "too_large",
                       "That %s is larger than the %s limit." % (SLOTS[kind]["noun"],
                                                                 LIMIT_WORDS[kind]),
                       {"limit": SLOTS[kind]["limit"], "bytes": length})


def part_path(app):
    return os.path.join(app.config.uploads, "%d-%s.part" % (os.getpid(), secrets.token_hex(8)))


def receive_upload(app, request, kind):
    """Stream the body to a .part file under work\\uploads and return its path."""
    length = request.content_length()
    check_size(kind, length)
    os.makedirs(app.config.uploads, exist_ok=True)
    return receive(request, length, part_path(app))


def sweep_parts(app):
    """Remove every .part file. Run at startup, when no upload can be in flight."""
    removed = 0
    try:
        names = os.listdir(app.config.uploads)
    except OSError:
        return 0
    for name in names:
        if name.endswith(".part"):
            try:
                os.remove(os.path.join(app.config.uploads, name))
                removed += 1
            except OSError:
                pass
    return removed


def discard(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def reply(app, request, project_id, status=200, **extra):
    """{project, ...extra}, or {} for ?quiet=1 on bulk uploads."""
    if request.flag("quiet"):
        return status, {}
    payload = {"project": snapshot.project(app, project_id)[1]}
    payload.update(extra)
    return status, payload


# --------------------------------------------------------------------------
# Audio and images
# --------------------------------------------------------------------------

def put(app, request, kind):
    """PUT /audio/{name} and /images/{name}: a new file, or a replacement with ?replace=1."""
    project_id = request.params["id"]
    project = projects.load(app, project_id)
    name = check_name(request.params["name"])
    check_extension(kind, name)
    check_size(kind, request.content_length())
    slot = SLOTS[kind]
    app.locks.check(project_id, slot["part"])
    folder = projects.folder(app, project_id, kind)
    replace = request.flag("replace")
    taken = find(folder, name)
    if taken and not replace:
        raise ApiError(409, "exists", "%s is already in this project. Replace it, or rename "
                       "the new one." % taken, {"name": taken})

    part = receive_upload(app, request, kind)
    try:
        with app.locks.project(project_id):
            app.locks.check(project_id, slot["part"])
            taken = find(folder, name)
            if taken and not replace:
                raise ApiError(409, "exists", "%s is already in this project." % taken,
                               {"name": taken})
            target = inside(folder, name)
            fence = app.locks.images(project_id).exclusive() if kind == "images" else _nothing()
            with fence:
                if taken:
                    trash.remove_files(app, project, slot["trash"], [inside(folder, taken)])
                os.replace(part, target)
    finally:
        discard(part)
    projects.touch(app, project_id)
    if kind == "images":
        app.thumbs.enqueue(target)
    return reply(app, request, project_id, 201)


def get(app, request, kind):
    """GET or HEAD a file: audio with Range, images with long caching when versioned."""
    project_id = request.params["id"]
    projects.load(app, project_id)
    folder, actual, path = existing(app, project_id, kind, request.params["name"])
    cache = "no-cache"
    if kind == "images":
        with app.locks.images(project_id).shared():
            wanted = request.query.get("v")
            if wanted and wanted == app.media.version(path):
                cache = "private, max-age=31536000, immutable"
            send_file(request.handler, path, content_type(actual),
                      head=request.method == "HEAD", cache=cache)
        return None
    send_file(request.handler, path, content_type(actual), head=request.method == "HEAD",
              cache=cache)
    return None


def delete(app, request, kind):
    project_id = request.params["id"]
    project = projects.load(app, project_id)
    slot = SLOTS[kind]
    app.locks.check(project_id, slot["part"])
    with app.locks.project(project_id):
        app.locks.check(project_id, slot["part"])
        folder, actual, path = existing(app, project_id, kind, request.params["name"])
        fence = app.locks.images(project_id).exclusive() if kind == "images" else _nothing()
        with fence:
            trash_id = trash.remove_files(app, project, slot["trash"], [path])
    projects.touch(app, project_id)
    return reply(app, request, project_id, 200, trashId=trash_id)


class _nothing:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# --------------------------------------------------------------------------
# Transcript
# --------------------------------------------------------------------------

def transcript_files(folder):
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return [os.path.join(folder, name) for name in names
            if os.path.isfile(os.path.join(folder, name))]


def current_transcript(app, project_id):
    return snapshot.choose_transcript(projects.folder(app, project_id, "transcript"))


def line_count(app, path):
    if not path:
        return 0
    lines, _ = app.media.transcript(path)
    return len(lines)


def _unreadable(error, part, name):
    message = str(error).replace(part, name)
    return ApiError(422, "blocked", "That transcript cannot be read, so nothing was changed. %s"
                    % message, {"blockers": [{"code": "transcript_unreadable",
                                              "message": message}]})


def put_transcript(app, request):
    """PUT /transcript/{name}: parse first, then replace whatever transcript was there."""
    project_id = request.params["id"]
    project = projects.load(app, project_id)
    name = check_name(request.params["name"])
    check_extension("transcript", name)
    check_size("transcript", request.content_length())
    app.locks.check(project_id, "transcript")
    part = receive_upload(app, request, "transcript")
    try:
        lines, error = app.media.transcript(part)
        if error:
            raise _unreadable(error, os.path.basename(part), name)
        with app.locks.project(project_id):
            app.locks.check(project_id, "transcript")
            folder = projects.folder(app, project_id, "transcript")
            before = line_count(app, current_transcript(app, project_id))
            old = transcript_files(folder)
            if old:
                trash.remove_files(app, project, "transcript", old)
            os.replace(part, inside(folder, name))
    finally:
        discard(part)
    projects.touch(app, project_id)
    return reply(app, request, project_id, 201, linesBefore=before, linesAfter=len(lines))


def text_version(data):
    return hashlib.sha1(data).hexdigest()[:16]


def get_raw(app, request):
    project_id = request.params["id"]
    projects.load(app, project_id)
    path = current_transcript(app, project_id)
    if not path:
        raise not_found("This project has no transcript yet.")
    with open(path, "rb") as handle:
        data = handle.read()
    return 200, {"name": os.path.basename(path),
                 "text": data.decode("utf-8-sig", errors="replace"),
                 "version": text_version(data)}


def put_raw(app, request):
    """PUT /transcript/raw: the edited text, refused if the file moved on meanwhile."""
    project_id = request.params["id"]
    project = projects.load(app, project_id)
    data = request.json(limit=16 * MB)
    text, version = data.get("text"), data.get("version")
    if not isinstance(text, str):
        raise invalid("Send the transcript as text.")
    if not isinstance(version, str):
        raise invalid("Send the version the edit started from.")
    encoded = text.encode("utf-8")
    check_size("transcript", len(encoded))
    app.locks.check(project_id, "transcript")
    path = current_transcript(app, project_id)
    if not path:
        raise not_found("This project has no transcript to edit.")

    os.makedirs(app.config.uploads, exist_ok=True)
    part = part_path(app)
    try:
        with open(part, "wb") as handle:
            handle.write(encoded)
        lines, error = app.media.transcript(part)
        if error:
            raise _unreadable(error, os.path.basename(part), os.path.basename(path))
        with app.locks.project(project_id):
            app.locks.check(project_id, "transcript")
            path = current_transcript(app, project_id)
            with open(path, "rb") as handle:
                current = text_version(handle.read())
            if current != version:
                raise ApiError(409, "changed",
                               "The transcript was changed somewhere else after you started "
                               "editing. Reload it, then make your edit again.",
                               {"what": "transcript", "version": current})
            before = line_count(app, path)
            trash.remove_files(app, project, "transcript", [path])
            os.replace(part, path)
    finally:
        discard(part)
    projects.touch(app, project_id)
    return reply(app, request, project_id, 200, linesBefore=before, linesAfter=len(lines))


def transcript_download_name(project, path):
    """transcript-<project name>-<when this transcript was made>, without an extension.

    The time is the transcript's own, not the moment of the click, so saving it
    twice gives one file rather than two, and two transcriptions of the same
    project are plainly different files.
    """
    try:
        made = time.localtime(os.path.getmtime(path))
    except OSError:
        made = time.localtime()
    return "transcript-%s-%s" % (projects.download_stem(project),
                                 time.strftime("%Y-%m-%d_%H-%M-%S", made))


def download_transcript(app, request):
    """GET /transcript/download?format=srt|txt, or the original file with no format."""
    project_id = request.params["id"]
    project = projects.load(app, project_id)
    path = current_transcript(app, project_id)
    if not path:
        raise not_found("This project has no transcript yet.")
    wanted = (request.query.get("format") or "").lower()
    if wanted not in ("", "srt", "txt"):
        raise invalid("format is srt or txt.")
    extension = os.path.splitext(path)[1].lower()
    stem = transcript_download_name(project, path)
    if not wanted or extension == "." + wanted:
        send_file(request.handler, path, content_type(path),
                  download=stem + extension, head=request.method == "HEAD")
        return None
    lines, error = app.media.transcript(path)
    if error:
        raise _unreadable(error, path, os.path.basename(path))
    total = snapshot.narration_seconds(app, project_id)
    starts = [start for start, _ in lines]
    ends = starts[1:] + [max(total or 0, starts[-1] + 1.0)]
    cues = [captions.make(start, end, text) for (start, text), end in zip(lines, ends)]
    body = (captions.to_srt(cues) if wanted == "srt" else captions.to_txt(cues)).encode("utf-8")
    respond(request.handler, 200, [("Content-Type", content_type("x." + wanted)),
                                   ("Content-Disposition", disposition(stem + "." + wanted)),
                                   ("Cache-Control", "no-cache")], body,
            head=request.method == "HEAD")
    return None


def delete_transcript(app, request):
    project_id = request.params["id"]
    project = projects.load(app, project_id)
    app.locks.check(project_id, "transcript")
    with app.locks.project(project_id):
        app.locks.check(project_id, "transcript")
        old = transcript_files(projects.folder(app, project_id, "transcript"))
        if not old:
            raise not_found("This project has no transcript to remove.")
        trash_id = trash.remove_files(app, project, "transcript", old)
    projects.touch(app, project_id)
    return reply(app, request, project_id, 200, trashId=trash_id)


def image_ref(app, project_id, path, info=None):
    """The ImageRef shape for one image on disk."""
    info = info or os.stat(path)
    name = os.path.basename(path)
    version = app.media.version(path, info)
    return {
        "name": name,
        "url": api_url("projects", project_id, "images", name) + "?v=" + version,
        "thumb": api_url("projects", project_id, "images", name, "thumb") + "?w=320&v=" + version,
        "bytes": info.st_size,
        "version": version,
    }
