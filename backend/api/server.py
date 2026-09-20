r"""The HTTP server: security checks, dispatch, startup and shutdown.

    from api import server
    running = server.serve(port=8765)      # returns once it is listening
    running.url                            # http://127.0.0.1:8765
    running.stop()                         # or server.stop(running)

It binds to 127.0.0.1 only and answers only requests addressed to
127.0.0.1:<port> or localhost:<port>, which is what stops a web page from
reaching it through DNS rebinding. Cross origin access is granted only to
http://localhost:* and http://127.0.0.1:*, and every request that changes
something must carry one of those origins when it carries one at all. POST and
PATCH must also be application/json, which a plain HTML form cannot send, so
the cross site text/plain POST that needs no preflight is closed too.

On startup, before it answers anything, it: sweeps half received uploads and
half built renders, purges trash older than seven days, puts itself in a job
object so no ffmpeg can outlive it, marks any job left running as interrupted,
imports the pre web app folders when running on the default storage, and tidies
away transcript copies that nothing reads.
"""

import re
import socket
import socketserver
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from i2v import paths, probe

from . import VERSION, files, legacy, render_job, routes, tidy, transcribe_job, trash
from .config import Config
from .httpio import DROPPED, ApiError, Request, invalid, respond, send_error, send_json
from .jobs import JobManager
from .locks import Locks
from .media import Media
from .thumbs import Thumbs

ORIGIN = re.compile(r"^http://(?:localhost|127\.0\.0\.1)(?::\d{1,5})?$")
MUTATIONS = ("POST", "PUT", "PATCH", "DELETE")
EXPOSE = "ETag, Content-Range, Content-Length, Content-Disposition, Accept-Ranges"
ALLOW_METHODS = "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS"
_HEADER_LIST = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]+(?:\s*,\s*[A-Za-z0-9!#$%&'*+.^_`|~-]+)*$")

# Means: import the old input and output folders only when storage is the default.
AUTO = object()


class App:
    """Everything one server shares: configuration, jobs, locks, caches, thumbnails."""

    def __init__(self, config):
        self.config = config
        self.media = Media(config)
        self.locks = Locks(self)
        self.jobs = JobManager(self)
        self.thumbs = Thumbs(self)
        self.guard = False
        self.imported = None

    def startup(self, legacy_root=None):
        self.config.ensure()
        files.sweep_parts(self)
        render_job.sweep(self)
        trash.purge(self)
        self.guard = probe.bind_children_to_this_process()
        for job in self.jobs.load():
            if job.kind == "transcribe":
                try:
                    transcribe_job.recover(self, job)
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
        if legacy_root:
            try:
                self.imported = legacy.import_legacy(self, legacy_root)
            except Exception:  # noqa: BLE001 - a failed import must not stop the server
                traceback.print_exc()
        # After the import, so anything it brought in is tidied as well.
        try:
            tidy.run(self)
        except Exception:  # noqa: BLE001 - housekeeping must not stop the server
            traceback.print_exc()
        self.thumbs.start()

    def shutdown(self):
        self.jobs.stop()
        self.thumbs.stop()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "img2vid/" + VERSION
    sys_version = ""
    # Seconds a connection may sit idle, including between blocks of an upload.
    timeout = 120

    def setup(self):
        super().setup()
        self.allowed_origin = None
        self.closing = False
        self.sent = False

    def log_message(self, format, *args):  # noqa: A002 - the base class's name
        pass

    def base_headers(self):
        headers = [("X-Content-Type-Options", "nosniff"), ("Vary", "Origin")]
        if self.allowed_origin:
            headers.append(("Access-Control-Allow-Origin", self.allowed_origin))
            headers.append(("Access-Control-Expose-Headers", EXPOSE))
        if self.closing:
            headers.append(("Connection", "close"))
        return headers

    def do_GET(self):
        self.dispatch("GET")

    def do_HEAD(self):
        self.dispatch("HEAD")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def do_PATCH(self):
        self.dispatch("PATCH")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def do_OPTIONS(self):
        self.dispatch("OPTIONS")

    def guard(self, request):
        port = self.server.server_address[1]
        host = (self.headers.get("Host") or "").strip().lower()
        if host not in ("127.0.0.1:%d" % port, "localhost:%d" % port):
            raise ApiError(403, "forbidden", "This server only answers requests addressed to "
                           "127.0.0.1:%d or localhost:%d." % (port, port))
        origin = self.headers.get("Origin")
        if origin is not None:
            if ORIGIN.match(origin):
                self.allowed_origin = origin
            elif request.method in MUTATIONS or request.method == "OPTIONS":
                raise ApiError(403, "forbidden", "Requests from %s are not allowed. Open the app "
                               "from localhost." % origin)
        if request.method in ("POST", "PATCH"):
            kind = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if kind != "application/json":
                raise invalid("Send this request with Content-Type: application/json.",
                              {"contentType": kind or None})

    def preflight(self, request):
        if not self.allowed_origin:
            raise ApiError(403, "forbidden", "Cross origin requests are only allowed from "
                           "localhost.")
        wanted = self.headers.get("Access-Control-Request-Headers") or ""
        allowed = wanted if _HEADER_LIST.match(wanted) else "Content-Type, If-None-Match, Range"
        headers = [("Access-Control-Allow-Methods", ALLOW_METHODS),
                   ("Access-Control-Allow-Headers", allowed),
                   ("Access-Control-Max-Age", "600")]
        if (self.headers.get("Access-Control-Request-Private-Network") or "").lower() == "true":
            headers.append(("Access-Control-Allow-Private-Network", "true"))
        request.settle()
        respond(self, 204, headers)

    def dispatch(self, method):
        self.allowed_origin = None
        self.closing = False
        self.sent = False
        request = None
        try:
            request = Request(self, method)
            self.guard(request)
            if method == "OPTIONS":
                self.preflight(request)
                return
            handler, params = routes.match(method, request.segments)
            request.params = params
            result = handler(self.server.app, request)
            if result is not None and not self.sent:
                request.settle()
                send_json(self, result[0], result[1], head=method == "HEAD")
        except ApiError as error:
            self.fail(request, error)
        except DROPPED:
            self.close_connection = True
        except Exception as error:  # noqa: BLE001 - becomes a 500 with the text
            traceback.print_exc()
            self.fail(request, ApiError(500, "internal", str(error) or type(error).__name__))
        finally:
            if request is not None and request.unread():
                self.close_connection = True

    def fail(self, request, error):
        if self.sent:
            # Headers are already out, so the only honest thing left is to hang up.
            self.close_connection = True
            return
        if request is not None:
            request.settle()
        try:
            send_error(self, error)
        except DROPPED:
            self.close_connection = True


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets a second process bind the same port and
    # steal half the connections. Exclusive use is asked for instead.
    allow_reuse_address = False
    request_queue_size = 64

    def __init__(self, app, port):
        self.app = app
        self.thread = None
        self._stopped = False
        super().__init__(("127.0.0.1", port), Handler)

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        # TCPServer's bind, not HTTPServer's, which looks the address up in DNS.
        socketserver.TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]

    @property
    def port(self):
        return self.server_address[1]

    @property
    def url(self):
        return "http://127.0.0.1:%d" % self.port

    def start(self):
        self.thread = threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.2},
                                       name="img2vid-api", daemon=True)
        self.thread.start()

    def stop(self):
        """Stop answering, cancel a running job, stop the thumbnail workers."""
        if self._stopped:
            return
        self._stopped = True
        if self.thread is not None:
            self.shutdown()
            self.thread.join(timeout=10)
        self.server_close()
        self.app.shutdown()


def serve(host="127.0.0.1", port=8765, storage=None, runtime=None, legacy_root=AUTO):
    """Start the API on a background thread and return the running Server.

    port 0 picks a free port, read back from `.port`. `storage` and `runtime`
    default to backend\\storage and backend\\runtime. `legacy_root` is where the
    old input and output folders are looked for: by default the project folder
    when storage is the default, and nowhere otherwise, so a test server never
    touches real files. Pass None to skip the import.
    """
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("The img2vid API only listens on 127.0.0.1.")
    if legacy_root is AUTO:
        legacy_root = paths.ROOT if storage is None else None
    app = App(Config(storage, runtime))
    # Bound before anything on disk is touched, so a second copy started by
    # mistake fails here instead of importing or sweeping alongside the first.
    server = Server(app, port)
    try:
        app.startup(legacy_root)
    except BaseException:
        server.server_close()
        raise
    server.start()
    return server


def stop(server):
    server.stop()

