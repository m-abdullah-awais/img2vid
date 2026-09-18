"""GET /api/projects/{id}: everything the project screen shows, in one object.

Computed in process from the engine's own functions, so the screen and the
render cannot disagree:

    placement      render.placement_report, the function the render uses
    gates          cli.missing_images_error for lines with no image, then the
                   RenderError that render.build_timeline raises, with .repair
    blockers       the same errors when they carry no repair

It is cached on the size and modification time of every file in the project
plus the state of its job. That key, hashed, is the ETag and the `version`, so
an unchanged project answers If-None-Match with 304 and costs one folder scan.
"""

import hashlib
import os
import re
import threading

from i2v import cli, paths, render

from . import files, projects, videos
from .httpio import api_url

# Bump when the shape changes, so a cached snapshot from the old shape is not reused.
SCHEMA = 1

_DIGITS = re.compile(r"^\d+")

_cache = {}
_cache_lock = threading.Lock()


class Facts:
    """What is on disk for one project, read once per snapshot."""

    def __init__(self, **values):
        self.__dict__.update(values)


def choose_transcript(folder):
    """The first .srt, else the first .vtt, else the first .txt, in natural order."""
    for extension in paths.TRANSCRIPT_EXTENSIONS:
        found = paths.listing(folder, (extension,))
        if found:
            return found[0]
    return None


def image_paths(folder):
    try:
        return render.find_images(folder)
    except render.RenderError:
        return []


def audio_paths(app, project_id):
    return paths.listing(projects.folder(app, project_id, "audio"), paths.AUDIO_EXTENSIONS)


def narration_seconds(app, project_id):
    durations = [app.media.duration(path) for path in audio_paths(app, project_id)]
    if not durations or None in durations:
        return None
    return float(sum(durations))


def gather(app, project_id):
    audio = audio_paths(app, project_id)
    durations = [app.media.duration(path) for path in audio]
    total = float(sum(durations)) if audio and None not in durations else None
    transcript_path = choose_transcript(projects.folder(app, project_id, "transcript"))
    lines, transcript_error = ([], None)
    if transcript_path:
        lines, transcript_error = app.media.transcript(transcript_path)
    images = image_paths(projects.folder(app, project_id, "images"))
    report = render.placement_report(images, len(lines))
    return Facts(project_id=project_id, audio=audio, durations=durations, total_audio=total,
                 transcript=transcript_path, transcript_error=transcript_error, lines=lines,
                 images=images, report=report, tools=app.media.tools() is not None)


# --------------------------------------------------------------------------
# Placement, in lines
# --------------------------------------------------------------------------

def base_of(report):
    return report["base"] if report["mode"] == "numbered" else 1


def placement(facts):
    """(by_line, line_of): the image path on each line, and each placed name's line."""
    count = len(facts.lines)
    report = facts.report
    by_line = [None] * count
    line_of = {}
    if report["mode"] == "numbered":
        for index, path in enumerate(report["slots"]):
            by_line[index] = path
            if path:
                line_of[os.path.basename(path)] = index + 1
    elif report["mode"] == "positional":
        for index, path in enumerate(facts.images[:count]):
            by_line[index] = path
            line_of[os.path.basename(path)] = index + 1
    return by_line, line_of


def missing_lines(facts):
    """Line numbers with no image. Filename numbers are converted, so base 0 is handled."""
    report = facts.report
    count = len(facts.lines)
    if report["mode"] == "numbered":
        return [number - report["base"] + 1 for number in report["missing"]]
    if report["mode"] == "positional":
        return list(range(len(facts.images) + 1, count + 1))
    return list(range(1, count + 1))


def duplicate_lines(facts):
    report = facts.report
    if report["mode"] != "numbered":
        return []
    return [{"line": clash["number"] - report["base"] + 1, "names": clash["names"]}
            for clash in report["duplicates"]]


def leading_digits(name):
    match = _DIGITS.match(name)
    return match.group() if match else ""


def width(facts):
    """Zero padding for new names: at least 3, as wide as the folder already uses."""
    report = facts.report
    count = len(facts.lines)
    widest = 3
    if report["mode"] == "numbered":
        for path in facts.images:
            widest = max(widest, len(leading_digits(os.path.basename(path))))
        highest = count - 1 + report["base"]
    else:
        highest = max(count, len(facts.images))
    return max(widest, len(str(max(0, highest))))


# --------------------------------------------------------------------------
# Gates and blockers, from the engine itself
# --------------------------------------------------------------------------

def _without_pass_line(text):
    lines = str(text).rstrip().splitlines()
    if lines and lines[-1].strip().startswith("Pass --"):
        lines = lines[:-1]
    return "\n".join(lines).rstrip()


def _video_hint(snap):
    """What the Video step says before the first build, as a status, not a question.

    A gate's own question ("Leave those 3 lines black and build the video?") is
    the right words inside the Build dialog and the wrong ones on a status line,
    where nothing is being asked yet.
    """
    if snap["blockers"]:
        return "Cannot build yet: %s" % snap["blockers"][0]["message"].splitlines()[0]
    for gate in snap["gates"]:
        if gate["repair"] == "--allow-black":
            count = len(gate.get("missing") or [])
            return ("Build will ask first, %d %s would be black."
                    % (count, "line" if count == 1 else "lines"))
        if gate["repair"] == "--force":
            return "Build will ask first, the images and lines do not match."
    return "Ready to build."


def _gate(error, missing=None):
    gate = {"repair": error.repair, "question": error.question,
            "message": _without_pass_line(error)}
    if missing is not None:
        gate["missing"] = missing
    return gate


def check(facts, fps):
    """(gates, blockers) for a render at this frame rate, exactly as the engine decides.

    Mirrors the CLI's order: placement first, the black line stop second, then
    build_timeline. A --force gate is followed by a forced build_timeline, so a
    failure that even --force cannot get past shows up as a blocker now rather
    than after the user has said yes.
    """
    blockers = []
    if not facts.audio:
        blockers.append({"code": "no_audio", "message": "Add the narration audio."})
    elif not facts.tools:
        blockers.append({"code": "ffmpeg_missing",
                         "message": "ffmpeg was not found. Run Setup.bat, which installs a "
                                    "private copy."})
    elif facts.total_audio is None:
        unreadable = [os.path.basename(path) for path, seconds
                      in zip(facts.audio, facts.durations) if seconds is None]
        blockers.append({"code": "audio_unreadable",
                         "message": "Could not read the length of %s. Replace it with a "
                                    "standard audio file." % ", ".join(unreadable)})
    if not facts.transcript:
        blockers.append({"code": "no_transcript",
                         "message": "Add a transcript, or transcribe the narration."})
    elif facts.transcript_error:
        blockers.append({"code": "transcript_unreadable", "message": facts.transcript_error})
    if not facts.images:
        blockers.append({"code": "no_images", "message": "Add the images, one per line."})
    if blockers:
        return [], blockers

    starts = [start for start, _ in facts.lines]
    report = facts.report
    gates = []
    timeline_images = list(facts.images)
    if report["mode"] == "numbered":
        if report["duplicates"]:
            try:
                render.place_by_index(facts.images, len(starts))
            except render.RenderError as error:
                blockers.append({"code": "duplicate", "message": str(error)})
            return gates, blockers
        timeline_images = list(report["slots"])
        if report["missing"]:
            lines = missing_lines(facts)
            gates.append(_gate(cli.missing_images_error(lines), missing=lines))

    try:
        render.build_timeline(starts, timeline_images, facts.total_audio, fps)
    except render.RenderError as error:
        if not error.repair:
            blockers.append({"code": "timeline", "message": str(error)})
        else:
            gates.append(_gate(error))
            if error.repair == "--force":
                try:
                    render.build_timeline(starts, timeline_images, facts.total_audio, fps,
                                          force=True)
                except render.RenderError as again:
                    blockers.append({"code": "timeline", "message": str(again)})
    return gates, blockers


# --------------------------------------------------------------------------
# The snapshot
# --------------------------------------------------------------------------

def fingerprint(app, project_id):
    """A hash of every file's stat in the project, plus its job's state."""
    base = projects.folder(app, project_id)
    parts = [SCHEMA]
    try:
        info = os.stat(os.path.join(base, "project.json"))
        parts.append(("project", info.st_size, info.st_mtime_ns))
    except OSError:
        parts.append(("project", None))
    for kind in projects.FOLDERS:
        folder = os.path.join(base, kind)
        try:
            parts.append((kind, os.stat(folder).st_mtime_ns))
        except OSError:
            parts.append((kind, None))
            continue
        entries = []
        try:
            with os.scandir(folder) as listing:
                for entry in listing:
                    try:
                        if entry.is_file():
                            info = entry.stat()
                            entries.append((entry.name, info.st_size, info.st_mtime_ns))
                    except OSError:
                        pass
        except OSError:
            pass
        parts.append(tuple(sorted(entries)))
    job = app.jobs.latest_for(project_id)
    if job is not None:
        progress = None if job.progress is None else round(job.progress, 2)
        parts.append((job.id, job.state, job.phase, progress))
    parts.append(app.media.tools() is not None)
    return hashlib.sha1(repr(parts).encode("utf-8", "replace")).hexdigest()[:16]


def project(app, project_id):
    """(version, Project), rebuilt only when the fingerprint moved."""
    stored = projects.load(app, project_id)
    key = fingerprint(app, project_id)
    with _cache_lock:
        cached = _cache.get((id(app), project_id))
    if cached and cached[0] == key:
        return cached
    with app.locks.images(project_id).shared():
        data = build(app, stored, key)
    result = (key, data)
    with _cache_lock:
        _cache[(id(app), project_id)] = result
    return result


def forget(app, project_id):
    with _cache_lock:
        _cache.pop((id(app), project_id), None)


def inputs_changed_at(facts, app, project_id):
    """The newest modification among the inputs and their folders, in nanoseconds.

    Folder times are included because a rename or a removal changes which image
    sits on which line without touching any file's own modification time.
    """
    newest = 0
    candidates = list(facts.audio) + list(facts.images)
    transcript_folder = projects.folder(app, project_id, "transcript")
    candidates += files.transcript_files(transcript_folder)
    candidates += [projects.folder(app, project_id, kind)
                   for kind in ("audio", "images", "transcript")]
    for path in candidates:
        try:
            newest = max(newest, os.stat(path).st_mtime_ns)
        except OSError:
            pass
    return newest


def clock(seconds):
    if seconds is None:
        return "unknown length"
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return "%d:%02d:%02d" % (hours, minutes, secs) if hours else "%d:%02d" % (minutes, secs)


def plural(count, word, many=None):
    return "%d %s" % (count, word if count == 1 else (many or word + "s"))


def build(app, stored, version):
    project_id = stored["id"]
    settings = stored["settings"]
    facts = gather(app, project_id)
    report = facts.report
    count = len(facts.lines)
    base = base_of(report)
    by_line, line_of = placement(facts)
    duplicates = duplicate_lines(facts)
    clashing = {entry["line"] for entry in duplicates}
    refs = {}

    def ref(path):
        if path not in refs:
            refs[path] = files.image_ref(app, project_id, path)
        return refs[path]

    storyboard = []
    for index, (start, text) in enumerate(facts.lines):
        if index + 1 < count:
            end = facts.lines[index + 1][0]
        elif facts.total_audio and facts.total_audio > start:
            end = facts.total_audio
        else:
            end = start
        path = by_line[index]
        state = "duplicate" if index + 1 in clashing else ("ok" if path else "missing")
        storyboard.append({
            "line": index + 1, "number": index + base,
            "start": round(start, 3), "end": round(end, 3), "seconds": round(end - start, 3),
            "text": text, "state": state, "image": ref(path) if path else None,
        })

    missing = missing_lines(facts)
    images = {
        "mode": report["mode"],
        "reason": report["reason"],
        "base": base,
        "width": width(facts),
        "total": len(facts.images),
        "placed": sum(1 for path in by_line if path),
        "missing": missing,
        "duplicates": duplicates,
        "unplaced": [ref(path) for path in facts.images
                     if os.path.basename(path) not in line_of],
    }

    gates, blockers = check(facts, settings["fps"])
    video_list = videos.listing(app, project_id, inputs_changed_at(facts, app, project_id))
    job = app.jobs.latest_for(project_id)
    job_dict = job.to_dict() if job else None
    locked = app.locks.state(project_id)

    audio_files = [{"name": os.path.basename(path),
                    "bytes": _size(path),
                    "seconds": None if seconds is None else round(seconds, 3),
                    "url": api_url("projects", project_id, "audio", os.path.basename(path))}
                   for path, seconds in zip(facts.audio, facts.durations)]

    transcript = None
    if facts.transcript:
        stale = False
        try:
            written = os.stat(facts.transcript).st_mtime_ns
            stale = any(os.stat(path).st_mtime_ns > written for path in facts.audio)
        except OSError:
            pass
        transcript = {"name": os.path.basename(facts.transcript), "lines": count,
                      "stale": stale,
                      "url": api_url("projects", project_id, "transcript", "download")}

    snapshot = {
        "id": project_id,
        "name": stored["name"],
        "createdAt": stored["createdAt"],
        "updatedAt": stored["updatedAt"],
        "version": version,
        "steps": None,
        "audio": {"files": audio_files,
                  "seconds": None if facts.total_audio is None else round(facts.total_audio, 3)},
        "transcript": transcript,
        "images": images,
        "storyboard": storyboard,
        "gates": gates,
        "blockers": blockers,
        "videos": video_list,
        "settings": settings,
        "job": job_dict,
        "locked": locked,
    }
    snapshot["steps"] = steps(facts, snapshot, job_dict)
    return snapshot


def _size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _running(job, kind):
    return job is not None and job["state"] == "running" and job["kind"] == kind


def _percent(job):
    return "" if job["progress"] is None else ", %d%%" % int(job["progress"] * 100)


def steps(facts, snap, job):
    audio = snap["audio"]
    transcript = snap["transcript"]
    images = snap["images"]

    if not facts.audio:
        narration = {"state": "missing", "summary": "No narration yet",
                     "detail": "Add one or more audio files. They play in filename order."}
    elif audio["seconds"] is None:
        narration = {"state": "attention", "summary": plural(len(facts.audio), "audio file"),
                     "detail": snap["blockers"][0]["message"] if snap["blockers"] else None}
    else:
        first = os.path.basename(facts.audio[0])
        summary = ("%s, %s" % (first, clock(audio["seconds"])) if len(facts.audio) == 1
                   else "%d files, %s" % (len(facts.audio), clock(audio["seconds"])))
        narration = {"state": "ready", "summary": summary, "detail": None}

    if _running(job, "transcribe"):
        script = {"state": "busy", "summary": "Transcribing%s" % _percent(job),
                  "detail": job["phase"]}
    elif transcript is None:
        script = {"state": "missing", "summary": "No transcript yet",
                  "detail": "Transcribe the narration, or add a .srt, .vtt or .txt file."}
    elif facts.transcript_error:
        script = {"state": "attention", "summary": "%s cannot be read" % transcript["name"],
                  "detail": facts.transcript_error}
    elif transcript["stale"]:
        script = {"state": "attention",
                  "summary": "%s, %s" % (transcript["name"], plural(transcript["lines"], "line")),
                  "detail": "The narration changed after this transcript was made."}
    else:
        script = {"state": "ready",
                  "summary": "%s, %s" % (transcript["name"], plural(transcript["lines"], "line")),
                  "detail": None}

    count = len(facts.lines)
    if not facts.images:
        pictures = {"state": "missing", "summary": "No images yet",
                    "detail": "Add one image per transcript line."}
    elif images["duplicates"]:
        first = images["duplicates"][0]
        pictures = {"state": "attention", "summary": plural(images["total"], "image"),
                    "detail": "%s claim line %d: %s" % (plural(len(first["names"]), "image"),
                                                        first["line"],
                                                        ", ".join(first["names"]))}
    elif not count:
        pictures = {"state": "ready", "summary": plural(images["total"], "image"),
                    "detail": "Add a transcript to put them on lines."}
    elif images["missing"]:
        pictures = {"state": "attention", "summary": plural(images["total"], "image"),
                    "detail": "%s no image" % ("1 line has" if len(images["missing"]) == 1
                                                else "%d lines have" % len(images["missing"]))}
    elif images["mode"] == "positional" and images["total"] != count:
        pictures = {"state": "attention", "summary": plural(images["total"], "image"),
                    "detail": "%s for %s" % (plural(images["total"], "image"),
                                             plural(count, "line"))}
    else:
        detail = None
        if images["mode"] == "positional":
            detail = "Paired in filename order, because the names are not numbered by line."
        pictures = {"state": "ready", "summary": "%s, one on every line"
                    % plural(images["total"], "image"), "detail": detail}

    newest = snap["videos"][0] if snap["videos"] else None
    if _running(job, "render"):
        video = {"state": "busy", "summary": "Building%s" % _percent(job), "detail": job["phase"]}
    elif newest is None:
        video = {"state": "missing", "summary": "No video yet",
                 "detail": _video_hint(snap)}
    elif newest["outdated"]:
        video = {"state": "attention", "summary": "%s, %s" % (newest["name"],
                                                             clock(newest["seconds"])),
                 "detail": "Something changed after it was built. Build it again to include it."}
    else:
        video = {"state": "ready", "summary": "%s, %s" % (newest["name"], clock(newest["seconds"])),
                 "detail": None}

    return {"narration": narration, "transcript": script, "images": pictures, "video": video}


def status(snap):
    job = snap["job"]
    images = snap["images"]
    if job and job["state"] == "running":
        text = "Building video" if job["kind"] == "render" else "Transcribing"
        return {"text": text, "tone": "busy"}
    if not snap["audio"]["files"] and not snap["transcript"] and not images["total"] \
            and not snap["videos"]:
        return {"text": "Not started", "tone": "idle"}
    if not snap["audio"]["files"]:
        return {"text": "Needs narration", "tone": "missing"}
    if not snap["transcript"]:
        return {"text": "Needs a transcript", "tone": "missing"}
    if not images["total"]:
        return {"text": "Needs images", "tone": "missing"}
    if images["missing"]:
        count = len(images["missing"])
        return {"text": "%s missing" % plural(count, "image"), "tone": "attention"}
    if snap["blockers"]:
        return {"text": "Cannot build yet", "tone": "attention"}
    if snap["gates"]:
        return {"text": "Needs a decision", "tone": "attention"}
    if snap["videos"]:
        if snap["videos"][0]["outdated"]:
            return {"text": "Video out of date", "tone": "attention"}
        return {"text": "Video built", "tone": "ready"}
    return {"text": "Ready to build", "tone": "ready"}


def summary(app, project_id):
    """The ProjectSummary shape, from the cached snapshot."""
    _, snap = project(app, project_id)
    images = snap["images"]
    cover = None
    first = [line["image"] for line in snap["storyboard"] if line["image"]]
    if first:
        cover = first[0]["thumb"]
    elif images["unplaced"]:
        cover = images["unplaced"][0]["thumb"]
    return {
        "id": snap["id"], "name": snap["name"],
        "createdAt": snap["createdAt"], "updatedAt": snap["updatedAt"],
        "cover": cover,
        "status": status(snap),
        "counts": {"lines": len(snap["storyboard"]), "images": images["total"],
                   "missing": len(images["missing"]), "videos": len(snap["videos"])},
        "seconds": snap["audio"]["seconds"],
    }
