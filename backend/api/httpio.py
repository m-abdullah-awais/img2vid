"""Reading requests and writing responses: JSON, errors, files with Range, uploads.

Every function that writes takes the request handler, which supplies the
headers every response carries (CORS, nosniff) through base_headers().
"""

import datetime
import json
import os
import re
import time
from email.utils import formatdate
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit

# Uploads and file responses move in blocks this size.
BLOCK = 1024 * 1024

# A JSON body bigger than this is refused before it is read. The transcript
# editor gets its own, larger allowance.
JSON_LIMIT = 1024 * 1024

# An unread body up to this size is read and thrown away before an error is
# sent, so the client finishes sending and then sees the answer. Anything
# larger closes the connection instead of reading gigabytes for nothing.
DRAIN_LIMIT = 64 * 1024 * 1024

# Aborted connections are routine: a video element that seeks drops the
# request it no longer needs.
DROPPED = (ConnectionAbortedError, BrokenPipeError, ConnectionResetError)

CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".wma": "audio/x-ms-wma",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".srt": "application/x-subrip; charset=utf-8",
    ".vtt": "text/vtt; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


class ApiError(Exception):
    """A failure with a status, a code from the contract, and a message for a person."""

    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    def payload(self):
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


def invalid(message, details=None):
    return ApiError(400, "invalid", message, details)


def not_found(message, details=None):
    return ApiError(404, "not_found", message, details)


def in_use(message=None):
    return ApiError(409, "in_use", message or (
        "Windows would not let that file be moved, usually because it is open "
        "somewhere, such as a video that is playing. Close it and try again."))


def content_type(name):
    return CONTENT_TYPES.get(os.path.splitext(name)[1].lower(), "application/octet-stream")


def iso(timestamp):
    """Seconds since the epoch as ISO 8601 in UTC with milliseconds and a Z."""
    moment = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (moment.microsecond // 1000)


def now_iso():
    return iso(time.time())


def parse_iso(text):
    """The inverse of iso(), for the timestamps this API wrote itself."""
    try:
        moment = datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ")
    except (TypeError, ValueError):
        return None
    return moment.replace(tzinfo=datetime.timezone.utc).timestamp()


def api_url(*parts, **query):
    """A path under /api/ with every part URL encoded, so a name is always one segment."""
    path = "/api/" + "/".join(quote(str(part), safe="") for part in parts)
    if query:
        path += "?" + urlencode(query)
    return path


class Request:
    """One request: its path segments, query, headers and body."""

    def __init__(self, handler, method):
        self.handler = handler
        self.method = method
        split = urlsplit(handler.path)
        trimmed = split.path.strip("/")
        # Split before decoding, so an encoded slash stays inside its segment
        # where the name check can see it and refuse it.
        self.segments = [unquote(part, errors="replace") for part in trimmed.split("/")] if trimmed else []
        self.query = {key: values[-1] for key, values in
                      parse_qs(split.query, keep_blank_values=True).items()}
        self.headers = handler.headers
        self.params = {}
        self._json = None
        chunked = "chunked" in (self.headers.get("Transfer-Encoding") or "").lower()
        self.chunked = chunked
        try:
            self._remaining = max(0, int(self.headers.get("Content-Length") or 0))
        except ValueError:
            self._remaining = 0

    def flag(self, name):
        return (self.query.get(name) or "").lower() in ("1", "true", "yes")

    def content_length(self):
        """The declared body size, required for an upload."""
        if self.chunked:
            raise invalid("Send the file with a Content-Length, not chunked.")
        value = self.headers.get("Content-Length")
        if value is None:
            raise invalid("Send the file with a Content-Length header.")
        try:
            length = int(value)
        except ValueError:
            raise invalid("Content-Length is not a number.")
        if length < 0:
            raise invalid("Content-Length is not a number.")
        return length

    def unread(self):
        return self._remaining

    def read(self, size):
        size = min(size, self._remaining)
        if size <= 0:
            return b""
        data = self.handler.rfile.read(size)
        self._remaining -= len(data)
        if len(data) < size:
            # The client stopped sending. Nothing more will arrive.
            self._remaining = 0
        return data

    def body(self, limit):
        length = self._remaining
        if length > limit:
            raise ApiError(413, "too_large", "That request is too large.",
                           {"limit": limit, "bytes": length})
        chunks = []
        while self._remaining > 0:
            chunk = self.read(min(BLOCK, self._remaining))
            if not chunk:
                break
            chunks.append(chunk)
        data = b"".join(chunks)
        if len(data) < length:
            raise invalid("The request stopped before the whole body arrived.")
        return data

    def json(self, limit=JSON_LIMIT):
        if self._json is not None:
            return self._json
        raw = self.body(limit)
        if not raw.strip():
            data = {}
        else:
            try:
                data = json.loads(raw.decode("utf-8-sig"))
            except (UnicodeDecodeError, ValueError):
                raise invalid("The request body is not valid JSON.")
        if not isinstance(data, dict):
            raise invalid("The request body must be a JSON object.")
        self._json = data
        return data

    def settle(self):
        """Deal with a body nobody read, before a response goes out.

        With keep-alive, unread bytes would be parsed as the next request. A
        small leftover is read and dropped, a large one closes the connection.
        """
        if self._remaining <= 0 and not self.chunked:
            return
        if self.chunked or self._remaining > DRAIN_LIMIT:
            self.handler.close_connection = True
            self.handler.closing = True
            return
        try:
            while self._remaining > 0:
                if not self.read(min(BLOCK, self._remaining)):
                    break
        except (OSError, ValueError):
            self.handler.close_connection = True
            self.handler.closing = True


def respond(handler, status, headers, body=b"", head=False):
    """Send a status line, the common headers, these headers, then the body."""
    handler.send_response(status)
    for key, value in handler.base_headers():
        handler.send_header(key, value)
    has_length = False
    for key, value in headers:
        handler.send_header(key, value)
        has_length = has_length or key.lower() == "content-length"
    if not has_length and status not in (204, 304):
        handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.sent = True
    if body and not head and status not in (204, 304):
        handler.wfile.write(body)


def send_json(handler, status, payload, headers=(), head=False):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    respond(handler, status, [("Content-Type", "application/json; charset=utf-8"),
                              ("Cache-Control", "no-store")] + list(headers), body, head)


def send_error(handler, error):
    send_json(handler, error.status, error.payload())


def disposition(name, kind="attachment"):
    """Content-Disposition with an ASCII fallback and the real name in RFC 5987 form."""
    fallback = "".join(ch if 32 <= ord(ch) < 127 and ch not in '"\\' else "_" for ch in name)
    return '%s; filename="%s"; filename*=UTF-8\'\'%s' % (kind, fallback, quote(name, safe=""))


_RANGE = re.compile(r"^\s*bytes\s*=\s*(\d*)\s*-\s*(\d*)\s*$", re.IGNORECASE)


def parse_range(header, size):
    """(start, end) inclusive, "unsatisfiable", or None to send the whole file.

    Only a single range is honoured. Several ranges, or anything that does not
    parse, is ignored and the whole file is sent, which RFC 9110 allows.
    """
    match = _RANGE.match(header or "")
    if not match:
        return None
    first, last = match.groups()
    if not first and not last:
        return None
    if not first:
        suffix = int(last)
        if suffix == 0 or size == 0:
            return "unsatisfiable"
        return max(0, size - suffix), size - 1
    start = int(first)
    if start >= size:
        return "unsatisfiable"
    end = int(last) if last else size - 1
    if end < start:
        return None
    return start, min(end, size - 1)


def send_file(handler, path, ctype=None, head=False, download=None, cache="no-cache"):
    """Serve a file, honouring a single byte range.

    The handle is opened and closed inside this call, so nothing stays open
    between requests. A client that goes away mid transfer is normal and is
    not an error.
    """
    try:
        handle = open(path, "rb")
    except FileNotFoundError:
        raise not_found("That file is not there any more.")
    except PermissionError:
        raise in_use("That file is in use and cannot be read right now.")
    with handle:
        info = os.fstat(handle.fileno())
        size = info.st_size
        headers = [
            ("Content-Type", ctype or content_type(path)),
            ("Accept-Ranges", "bytes"),
            ("Cache-Control", cache),
            ("Last-Modified", formatdate(info.st_mtime, usegmt=True)),
        ]
        if download:
            headers.append(("Content-Disposition", disposition(download)))
        wanted = handler.headers.get("Range")
        span = parse_range(wanted, size) if wanted else None
        if span == "unsatisfiable":
            error = ApiError(416, "invalid", "That byte range is outside the file.",
                             {"bytes": size})
            body = json.dumps(error.payload()).encode("utf-8")
            respond(handler, 416, [("Content-Type", "application/json; charset=utf-8"),
                                   ("Content-Range", "bytes */%d" % size)], body, head)
            return
        if span:
            start, end = span
            status = 206
            headers.append(("Content-Range", "bytes %d-%d/%d" % (start, end, size)))
        else:
            start, end = 0, size - 1
            status = 200
        length = max(0, end - start + 1)
        headers.append(("Content-Length", str(length)))
        respond(handler, status, headers, head=True)
        if head or not length:
            return
        handle.seek(start)
        remaining = length
        try:
            while remaining > 0:
                chunk = handle.read(min(BLOCK, remaining))
                if not chunk:
                    break
                handler.wfile.write(chunk)
                remaining -= len(chunk)
        except DROPPED:
            handler.close_connection = True
        if remaining:
            # Promised more than was sent. The connection cannot be reused.
            handler.close_connection = True


def receive(request, length, destination):
    """Stream an upload body into destination in BLOCK sized pieces.

    The caller names a .part file and renames it into place afterwards, so a
    half received upload never appears under its real name.
    """
    received = 0
    try:
        with open(destination, "wb") as out:
            while received < length:
                chunk = request.read(min(BLOCK, length - received))
                if not chunk:
                    break
                out.write(chunk)
                received += len(chunk)
    except DROPPED:
        received = -1
    except BaseException:
        _remove(destination)
        raise
    if received != length:
        _remove(destination)
        request.handler.close_connection = True
        raise invalid("The upload stopped before the whole file arrived. Try again.")
    return destination


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass
