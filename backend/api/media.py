"""Facts about files that cost a process or a read to learn, cached on the stat.

Three of them: an audio or video duration (one ffprobe), an image's content
version (a hash of its first 64 KB), and a transcript's parsed lines. Each is
keyed on size, modification time and file id, so a rename reuses the answer
and any change to the content invalidates it.
"""

import hashlib
import os
import subprocess
import threading
import time

from i2v import probe, transcript

# Enough of a file to tell two images apart without reading all of it.
HEAD_BYTES = 64 * 1024

# How long to wait before looking for ffmpeg again after it was not found.
RETRY_TOOLS = 30.0

# Caches are dropped wholesale past this many entries, which only a very long
# running server with thousands of files would ever reach.
LIMIT = 50000


def stat_key(info):
    return (info.st_size, info.st_mtime_ns, info.st_ino, info.st_dev)


class Media:
    def __init__(self, config):
        self.config = config
        self._lock = threading.Lock()
        self._durations = {}
        self._versions = {}
        self._transcripts = {}
        self._tools = None
        self._looked = 0.0

    def tools(self):
        """ffmpeg and ffprobe, the private copy first, or None when neither exists."""
        with self._lock:
            if self._tools is not None:
                return self._tools
            if self._looked and time.monotonic() - self._looked < RETRY_TOOLS:
                return None
            self._looked = time.monotonic()
        try:
            tools = probe.Tools(self.config.bin)
        except probe.ProbeError:
            return None
        with self._lock:
            self._tools = tools
        return tools

    def forget_tools(self):
        with self._lock:
            self._tools = None
            self._looked = 0.0

    def _remember(self, cache, key, value):
        with self._lock:
            if len(cache) > LIMIT:
                cache.clear()
            cache[key] = value

    def duration(self, path):
        """Seconds, or None when the file cannot be read or ffprobe is missing."""
        try:
            key = stat_key(os.stat(path))
        except OSError:
            return None
        with self._lock:
            if key in self._durations:
                return self._durations[key]
        tools = self.tools()
        if tools is None:
            return None
        try:
            seconds = probe.duration(tools, path)
        except (probe.ProbeError, OSError, subprocess.SubprocessError, ValueError):
            seconds = None
        self._remember(self._durations, key, seconds)
        return seconds

    def version(self, path, info=None):
        """A short hash of the size and the first 64 KB. Survives a rename."""
        info = info or os.stat(path)
        key = stat_key(info)
        with self._lock:
            if key in self._versions:
                return self._versions[key]
        digest = hashlib.sha1(b"%d:" % info.st_size)
        with open(path, "rb") as handle:
            digest.update(handle.read(HEAD_BYTES))
        value = digest.hexdigest()[:16]
        self._remember(self._versions, key, value)
        return value

    def transcript(self, path):
        """(lines, error): the parsed (start, text) pairs, or the reason it failed."""
        try:
            key = stat_key(os.stat(path))
        except OSError as error:
            return [], str(error)
        with self._lock:
            if key in self._transcripts:
                return self._transcripts[key]
        try:
            result = (transcript.parse(path), None)
        except (transcript.TranscriptError, OSError, ValueError) as error:
            result = ([], str(error).replace(path, os.path.basename(path)))
        self._remember(self._transcripts, key, result)
        return result
