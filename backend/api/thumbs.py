r"""Image thumbnails: made by ffmpeg, cached by content, never allowed near a render.

    ffmpeg -i <image> -vf scale=W:-2 -frames:v 1 -q:v 4 <thumb>.jpg

A thumbnail is cached in work\thumbs under the image's content version (its
size and a hash of its first 64 KB) and the width, never under its name. So a
rename, a renumber or an arrange reuses every thumbnail it already has.

At most two thumbnail ffmpeg processes run at once. Uploads queue the 320 wide
one in the background so the storyboard is ready by the time it is shown.

While any job runs the queue pauses, because nothing may take CPU from a
render or a transcription. A request for a thumbnail that is not cached yet then
gets the original file instead, when the browser can show it (JPEG, PNG, WebP).
Only BMP and TIFF, which a browser cannot show, are generated regardless.
"""

import collections
import os
import secrets
import subprocess
import threading

from i2v import probe

from . import files, projects
from .httpio import content_type, invalid, send_file

# Up to 1920 because the preview shows TIFF, which no browser can, through a
# thumbnail as wide as the stage. Every other format is shown as it is.
WIDTHS = (80, 1920)
BACKGROUND_WIDTH = 320
CONCURRENT = 2
BROWSER_SHOWS = (".jpg", ".jpeg", ".png", ".webp")


class Thumbs:
    def __init__(self, app):
        self.app = app
        self._slots = threading.Semaphore(CONCURRENT)
        self._cond = threading.Condition()
        self._queue = collections.deque()
        self._queued = set()
        self._making = {}
        self._making_lock = threading.Lock()
        self._workers = []
        self._stopping = False
        self.generated = 0

    # ---------------------------------------------------------------- workers

    def start(self):
        for number in range(CONCURRENT):
            worker = threading.Thread(target=self._work, name="thumbs-%d" % number, daemon=True)
            worker.start()
            self._workers.append(worker)

    def stop(self):
        with self._cond:
            self._stopping = True
            self._cond.notify_all()
        for worker in self._workers:
            worker.join(timeout=5)

    def enqueue(self, path, width=BACKGROUND_WIDTH):
        key = (os.path.normcase(path), width)
        with self._cond:
            if key in self._queued:
                return
            self._queued.add(key)
            self._queue.append((path, width))
            self._cond.notify()

    def pending(self):
        with self._cond:
            return len(self._queue)

    def slot(self):
        """One of the ffmpeg slots, for other one off media work such as the preview."""
        return self._slots

    def _paused(self):
        return self.app.jobs.running() is not None

    def _work(self):
        while True:
            with self._cond:
                while not self._stopping and (not self._queue or self._paused()):
                    self._cond.wait(0.5)
                if self._stopping:
                    return
                path, width = self._queue.popleft()
                self._queued.discard((os.path.normcase(path), width))
            try:
                project_id = self._project_of(path)
                if project_id and os.path.isfile(path):
                    with self.app.locks.images(project_id).shared():
                        if os.path.isfile(path):
                            self.make(path, width)
            except Exception:  # noqa: BLE001 - one bad image must not stop the queue
                pass

    def _project_of(self, path):
        relative = os.path.relpath(path, self.app.config.projects)
        parts = relative.split(os.sep)
        return parts[0] if len(parts) == 3 and parts[1] == "images" else None

    # ---------------------------------------------------------------- making

    def cached(self, version, width):
        return os.path.join(self.app.config.thumbs, "%s-%d.jpg" % (version, width))

    def make(self, path, width):
        """The cached thumbnail's path, generating it first when needed."""
        version = self.app.media.version(path)
        target = self.cached(version, width)
        if os.path.isfile(target):
            return target
        key = (version, width)
        with self._making_lock:
            waiting = self._making.get(key)
            if waiting is None:
                waiting = self._making[key] = threading.Event()
                mine = True
            else:
                mine = False
        if not mine:
            waiting.wait(60)
            return target if os.path.isfile(target) else None
        try:
            with self._slots:
                if not os.path.isfile(target):
                    self._generate(path, target, width)
            return target if os.path.isfile(target) else None
        finally:
            with self._making_lock:
                self._making.pop(key, None)
            waiting.set()

    def _generate(self, source, target, width):
        tools = self.app.media.tools()
        if tools is None:
            return
        os.makedirs(os.path.dirname(target), exist_ok=True)
        temporary = "%s.%s.tmp.jpg" % (target[:-4], secrets.token_hex(4))
        try:
            result = subprocess.run(
                [tools.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", source,
                 "-vf", "scale=%d:-2" % width, "-frames:v", "1", "-q:v", "4", temporary],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=60, creationflags=probe.NO_WINDOW)
            if result.returncode == 0 and os.path.isfile(temporary):
                os.replace(temporary, target)
                self.generated += 1
        except (OSError, subprocess.SubprocessError):
            pass
        finally:
            if os.path.exists(temporary):
                try:
                    os.remove(temporary)
                except OSError:
                    pass


def route(app, request):
    """GET /api/projects/{id}/images/{name}/thumb?w=320"""
    project_id = request.params["id"]
    projects.load(app, project_id)
    try:
        width = int(request.query.get("w") or BACKGROUND_WIDTH)
    except ValueError:
        raise invalid("w must be a number from %d to %d." % WIDTHS)
    if not WIDTHS[0] <= width <= WIDTHS[1]:
        raise invalid("w must be a number from %d to %d." % WIDTHS)
    head = request.method == "HEAD"
    with app.locks.images(project_id).shared():
        _, actual, path = files.existing(app, project_id, "images", request.params["name"])
        version = app.media.version(path)
        target = app.thumbs.cached(version, width)
        immutable = request.query.get("v") == version
        cache = "private, max-age=31536000, immutable" if immutable else "no-cache"
        if os.path.isfile(target):
            send_file(request.handler, target, "image/jpeg", head=head, cache=cache)
            return None
        if app.jobs.running() is not None and actual.lower().endswith(BROWSER_SHOWS):
            # Not cached and a job is running: the original, and not cached by
            # the browser, so the real thumbnail replaces it later.
            send_file(request.handler, path, content_type(actual), head=head, cache="no-store")
            return None
        made = app.thumbs.make(path, width)
    if made and os.path.isfile(made):
        send_file(request.handler, made, "image/jpeg", head=head, cache=cache)
        return None
    if actual.lower().endswith(BROWSER_SHOWS):
        send_file(request.handler, path, content_type(actual), head=head, cache="no-store")
        return None
    from .httpio import ApiError  # noqa: PLC0415
    raise ApiError(500, "internal", "Could not make a thumbnail of %s." % actual)
