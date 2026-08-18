"""Transcript parsing.

Supports SRT, WebVTT and plain line leading timestamps. Only the start time of
each cue is used. Each segment is later extended to the start of the next one,
so any end times in the source file are deliberately ignored. That is what
guarantees a gapless video with no black frames between images.
"""

import re

# Matches [HH:]MM:SS[.,mmm]. The hour group is optional so "1:23" works.
_TIME = r"(?:(\d+):)?(\d{1,3}):(\d{1,2})(?:[.,](\d{1,3}))?"

_CUE_RE = re.compile(r"^\s*" + _TIME + r"\s*-->\s*" + _TIME)
_LEADING_RE = re.compile(r"^\s*[\[\(<]?\s*" + _TIME + r"\s*[\]\)>]?\s*[-:\u2013]?\s*(.*)$")
_INDEX_RE = re.compile(r"^\s*\d+\s*$")


class TranscriptError(ValueError):
    """Raised when a transcript cannot be parsed into usable segments."""


def _to_seconds(hours, minutes, seconds, millis):
    total = int(minutes) * 60 + int(seconds)
    if hours:
        total += int(hours) * 3600
    if millis:
        # "5" means 500ms, "05" means 50ms, "005" means 5ms.
        total += int(millis) / (10 ** len(millis))
    return float(total)


def _read(path):
    # Transcripts routinely arrive with a BOM from Windows editors.
    with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
        return handle.read()


def _parse_cues(text):
    """Parse SRT or WebVTT. Both use the '-->' timing line."""
    segments = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = _CUE_RE.match(lines[index])
        if not match:
            index += 1
            continue
        start = _to_seconds(*match.groups()[:4])
        index += 1
        body = []
        while index < len(lines) and lines[index].strip():
            body.append(lines[index].strip())
            index += 1
        segments.append((start, " ".join(body)))
    return segments


def _parse_plain(text):
    """Parse lines that begin with a timestamp, such as '[0:01:23] some text'."""
    segments = []
    for line in text.splitlines():
        if not line.strip() or _INDEX_RE.match(line):
            continue
        match = _LEADING_RE.match(line)
        if not match:
            continue
        groups = match.groups()
        segments.append((_to_seconds(*groups[:4]), groups[4].strip()))
    return segments


def parse(path):
    """Return a list of (start_seconds, text), sorted and de-duplicated.

    Raises TranscriptError if nothing usable is found or the times are invalid.
    """
    text = _read(path)
    kind = "cue" if "-->" in text else "plain"
    segments = _parse_cues(text) if kind == "cue" else _parse_plain(text)

    if not segments:
        raise TranscriptError(
            "No timestamps found in %s. Expected SRT, WebVTT, or lines that "
            "start with a timestamp such as '[0:01:23] text'." % path
        )

    segments.sort(key=lambda item: item[0])

    # Two cues at the identical second would produce a zero length image.
    unique = []
    for start, body in segments:
        if unique and abs(start - unique[-1][0]) < 1e-9:
            continue
        unique.append((start, body))

    if unique[0][0] < 0:
        raise TranscriptError("Transcript contains a negative timestamp.")

    return unique
