r"""Reading a script's console output as it arrives: progress, phase, log, error.

The scripts write for a person at a console, so this reads the same text a
person would see. Output is split on both carriage returns and newlines, since
the progress bar redraws itself with \r and Python on Windows ends every
printed line with \r\n.

    progress   the engine's own bar, "  [######........] 42.0%  3.1s". The
               pattern is anchored and wants exactly thirty # or . characters,
               so a model download bar from huggingface never matches it
    phase      named from lines the engine prints at each stage
    events     every other non empty line, for the log
    error      the "error:" block the scripts print last before exiting
"""

import codecs
import re
import time

PROGRESS = re.compile(r"^\s*\[[#.]{30}\]\s+(\d+(?:\.\d+)?)%")

_SPLIT = re.compile(r"(\r\n|\r|\n)")

# Checked in order. The download line also starts with "model      :", so it
# has to be recognised before the plain model line is.
PHASES = (
    (re.compile(r"is not on this machine yet, fetching"), "Downloading model"),
    (re.compile(r"first run: timing the available encoders"), "Timing encoders"),
    (re.compile(r"\bencoding \d+ frames\b"), "Encoding"),
    (re.compile(r"\bjoining \d+ audio files\b"), "Joining audio"),
    (re.compile(r"^model\s+:"), "Transcribing"),
    (re.compile(r"^cached\s+:"), "Using the earlier transcription"),
)

# A line that redraws itself with \r, and is not the engine's bar, is logged at
# most this often, so a download bar does not flood the log.
REDRAW_GAP = 1.0


def phase_of(line):
    text = line.strip()
    for pattern, phase in PHASES:
        if pattern.search(text):
            return phase
    return None


class OutputParser:
    def __init__(self, on_progress, on_line, on_phase):
        self._on_progress = on_progress
        self._on_line = on_line
        self._on_phase = on_phase
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._pending = ""
        self._error = None
        self._last_redraw = 0.0

    @property
    def error(self):
        if not self._error:
            return None
        text = "\n".join(self._error).strip()
        return text or None

    def feed(self, data):
        text = self._pending + self._decoder.decode(data)
        # A trailing \r may be the first half of \r\n, so it waits for the next read.
        held = ""
        if text.endswith("\r"):
            text, held = text[:-1], "\r"
        parts = _SPLIT.split(text)
        pieces, separators = parts[0::2], parts[1::2]
        for piece, separator in zip(pieces, separators):
            self._piece(piece, redraw=separator == "\r")
        self._pending = pieces[-1] + held
        # The bar is written without a line ending, so it is read as soon as it
        # arrives rather than when the next redraw pushes it out.
        match = PROGRESS.match(self._pending.lstrip("\r"))
        if match:
            self._on_progress(float(match.group(1)) / 100.0)

    def close(self):
        text = self._pending + self._decoder.decode(b"", final=True)
        self._pending = ""
        for piece in _SPLIT.split(text)[0::2]:
            self._piece(piece, redraw=False)

    def _piece(self, piece, redraw):
        line = piece.rstrip()
        if not line.strip():
            return
        match = PROGRESS.match(line)
        if match:
            self._on_progress(float(match.group(1)) / 100.0)
            return
        if redraw:
            now = time.monotonic()
            if now - self._last_redraw < REDRAW_GAP:
                return
            self._last_redraw = now
        phase = phase_of(line)
        if phase:
            self._on_phase(phase)
        stripped = line.strip()
        if self._error is not None:
            self._error.append(line)
        elif stripped.startswith("error:"):
            self._error = [stripped[len("error:"):].strip()]
        self._on_line(line)
