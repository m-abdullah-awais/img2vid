r"""POST /api/projects/{id}/render: build the video with the engine's own script.

The render is backend\cli\img2vid.py, the same command a terminal would run:

    img2vid.py -t <transcript> -i <images> -a <audio...> -o work\renders\<id>-<stamp>.mp4
               --fps --size --fit --bg [--allow-black] [--force]

No --quiet, because its progress bar is where the progress comes from. No
--encoder and no --jobs, because the engine's defaults are the measured fast
path, and a render from the app must be exactly as fast as one from a terminal.

The gates are checked again here, in process, before anything starts. A flag is
only passed when its gate is present and the request confirmed it, and
--allow-black additionally needs confirmedMissing to equal the lines that are
missing right now, so a file removed after the question was shown can never go
black without being asked about.

The output is written under work\renders and only moved into the project's
videos folder once the script reports success. A failed or cancelled build
never appears there.
"""

import os
import re
import time

from i2v import captions

from . import projects, snapshot, videos
from .httpio import ApiError, invalid, iso

_SIZE = re.compile(r"^(\d{2,5})x(\d{2,5})$")
_COLOUR = re.compile(r"^(?:[A-Za-z]{1,32}|(?:#|0x)[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?)$")


def parse_settings(body, current):
    """RenderSettings from the request, falling back to the project's last used ones."""
    fps = body.get("fps", current["fps"])
    if isinstance(fps, bool) or not isinstance(fps, (int, float)) or int(fps) != fps \
            or not 1 <= fps <= 120:
        raise invalid("fps must be a whole number from 1 to 120.", {"field": "fps"})
    size = body.get("size", current["size"])
    match = _SIZE.match(size) if isinstance(size, str) else None
    if not match:
        raise invalid("size must look like 1920x1080.", {"field": "size"})
    width, height = int(match.group(1)), int(match.group(2))
    if not (16 <= width <= 7680 and 16 <= height <= 7680):
        raise invalid("Each side of size must be between 16 and 7680.", {"field": "size"})
    fit = body.get("fit", current["fit"])
    if fit not in ("contain", "cover"):
        raise invalid("fit must be contain or cover.", {"field": "fit"})
    background = body.get("background", current["background"])
    # Checked strictly: it is spliced into an ffmpeg filter graph.
    if not isinstance(background, str) or not _COLOUR.match(background):
        raise invalid("background must be a colour name such as black, or a hex colour "
                      "such as #1a1a1a.", {"field": "background"})
    return {"fps": int(fps), "size": "%dx%d" % (width, height), "fit": fit,
            "background": background,
            "captions": parse_captions(body.get("captions"), current["captions"])}


def parse_captions(given, current):
    """The caption settings, falling back to the project's last used ones."""
    if given is None:
        return dict(current)
    if not isinstance(given, dict):
        raise invalid("captions must be an object.", {"field": "captions"})
    merged = dict(current)
    merged.update({key: given[key] for key in current if key in given})
    if not isinstance(merged["on"], bool):
        raise invalid("captions.on must be true or false.", {"field": "captions.on"})
    if merged["place"] not in captions.PLACES:
        raise invalid("captions.place must be one of: %s." % ", ".join(sorted(captions.PLACES)),
                      {"field": "captions.place"})
    if merged["size"] not in captions.SIZES:
        raise invalid("captions.size must be one of: %s." % ", ".join(sorted(captions.SIZES)),
                      {"field": "captions.size"})
    if merged["look"] not in captions.BORDERS:
        raise invalid("captions.look must be one of: %s." % ", ".join(sorted(captions.BORDERS)),
                      {"field": "captions.look"})
    distance = merged["distance"]
    if isinstance(distance, bool) or not isinstance(distance, (int, float)) \
            or not 0 <= distance <= 45:
        raise invalid("captions.distance is a percentage of the frame height, 0 to 45.",
                      {"field": "captions.distance"})
    merged["distance"] = round(float(distance), 1)
    return merged


def _confirmed_lines(body):
    value = body.get("confirmedMissing")
    if value is None:
        return None
    if not isinstance(value, list) or not all(
            isinstance(item, int) and not isinstance(item, bool) for item in value):
        raise invalid("confirmedMissing must be a list of line numbers.",
                      {"field": "confirmedMissing"})
    return sorted(value)


def start(app, request):
    project_id = request.params["id"]
    body = request.json()
    stored = projects.load(app, project_id)
    settings = parse_settings(body, stored["settings"])
    allow_black = body.get("allowBlack") is True
    force = body.get("force") is True
    confirmed = _confirmed_lines(body)

    with app.jobs.begin() as jobs:
        with app.locks.project(project_id):
            stored = projects.load(app, project_id)
            facts = snapshot.gather(app, project_id)
            gates, blockers = snapshot.check(facts, settings["fps"])
            if blockers:
                raise ApiError(422, "blocked", blockers[0]["message"], {"blockers": blockers})
            flags, waiting = [], []
            for gate in gates:
                if gate["repair"] == "--allow-black":
                    if allow_black and confirmed == gate["missing"]:
                        flags.append("--allow-black")
                    else:
                        waiting.append(gate)
                elif gate["repair"] == "--force":
                    if force:
                        flags.append("--force")
                    else:
                        waiting.append(gate)
                else:
                    waiting.append(gate)
            if waiting:
                raise ApiError(409, "needs_confirmation", waiting[0]["question"],
                               {"gates": gates})

            os.makedirs(app.config.renders, exist_ok=True)
            output = os.path.join(app.config.renders, "%s-%s.mp4"
                                  % (project_id, time.strftime("%Y%m%d-%H%M%S")))
            args = ["-t", facts.transcript,
                    "-i", projects.folder(app, project_id, "images"),
                    "-a"] + list(facts.audio) + [
                    "-o", output,
                    "--fps", settings["fps"], "--size", settings["size"],
                    "--fit", settings["fit"], "--bg", settings["background"]] + flags
            spoken = settings["captions"]
            if spoken["on"]:
                args += ["--captions",
                         "--caption-place", spoken["place"],
                         "--caption-distance", spoken["distance"],
                         "--caption-size", spoken["size"],
                         "--caption-look", spoken["look"]]
            projects.update(app, project_id, settings=settings)

            def finish(job, state):
                return _finish(app, project_id, output, settings, job, state)

            job = jobs.launch("render", "img2vid.py", args, project=stored, finish=finish,
                              keep={"output": output})
    return 202, {"job": job.to_dict()}


def _done_line(job, output):
    for line in reversed(job.tail):
        text = line.strip()
        if text.startswith("done in"):
            return text
    return None


def _finish(app, project_id, output, settings, job, state):
    if state != "done":
        _remove(output)
        return state
    if not os.path.isfile(output):
        job.error = "The render reported success but no video file was written."
        return "failed"
    where = videos.folder(app, project_id)
    os.makedirs(where, exist_ok=True)
    with app.locks.project(project_id):
        name = videos.free_name(where, time.strftime("%Y-%m-%d_%H-%M-%S"))
        target = os.path.join(where, name)
        try:
            os.replace(output, target)
        except OSError as error:
            _remove(output)
            job.error = "The video was built but could not be moved into the project: %s" % error
            return "failed"
        line = _done_line(job, output)
        summary = line.replace(output, name) if line else None
        videos.put_meta(app, project_id, name, {"summary": summary, "createdAt": iso(time.time()),
                                               "settings": settings, "jobId": job.id})
    projects.touch(app, project_id)
    info = os.stat(target)
    video = videos.ref(app, project_id, target, info, videos.read_meta(app, project_id).get(name),
                       0)
    job.result = {"video": video, "summary": summary}
    return state


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def sweep(app):
    """Remove half built videos left in work\\renders by a server that was stopped."""
    try:
        names = os.listdir(app.config.renders)
    except OSError:
        return 0
    removed = 0
    for name in names:
        if name.lower().endswith(".mp4"):
            _remove(os.path.join(app.config.renders, name))
            removed += 1
    return removed
