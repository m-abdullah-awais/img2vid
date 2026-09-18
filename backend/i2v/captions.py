"""Caption cues: the shared timestamped segment type, its writers and re-splitting.

A cue is one line of transcript with a start time, an end time and some text. In
this project one cue becomes one image, so cue length is what decides how many
images the finished video needs.

A cue is a plain dict, so it serialises to JSON with no conversion step:

    {"start": 0.0, "end": 3.6, "text": "Right now, there is an address you type"}

An optional "words" list of {"start", "end", "word"} rides along when the speech
engine was asked for word level timings.

This module is the single place SRT is written, and it is standard library only.
It knows nothing about speech recognition, so anything can use it.
"""

import json

# SRT and VTT differ only in the character before the milliseconds.
SRT_SEPARATOR = ","
VTT_SEPARATOR = "."


def clock(seconds, separator=SRT_SEPARATOR):
    """Seconds to HH:MM:SS,mmm. Rounds to the nearest millisecond."""
    total = max(0, int(round(float(seconds) * 1000)))
    return "%02d:%02d:%02d%s%03d" % (
        total // 3600000, (total // 60000) % 60, (total // 1000) % 60,
        separator, total % 1000,
    )


def short_clock(seconds):
    """Seconds to HH:MM:SS, no milliseconds. For the readable transcript."""
    total = max(0, int(float(seconds)))
    return "%02d:%02d:%02d" % (total // 3600, (total // 60) % 60, total % 60)


def clean(text):
    """Collapse runs of whitespace and trim."""
    return " ".join((text or "").split())


def make(start, end, text, words=None):
    """Build one cue. Timings are rounded to 2 decimals, since finer is noise."""
    cue = {"start": round(float(start), 2), "end": round(float(end), 2), "text": clean(text)}
    if words:
        cue["words"] = words
    return cue


def _hold(value, duration):
    value = max(0.0, float(value))
    if duration is not None:
        value = min(value, float(duration))
    return value


def clamp(cues, duration=None):
    """Drop empty and zero length cues, and hold every time inside the audio.

    Speech recognition overshoots the true end of a file, most often on the final
    segment, so without this the captions can claim to run past the audio.
    """
    kept = []
    for cue in cues:
        text = clean(cue.get("text"))
        if not text:
            continue
        start = _hold(cue["start"], duration)
        end = _hold(cue["end"], duration)
        if end <= start:
            continue
        words = None
        if cue.get("words"):
            words = [
                {"start": round(_hold(word["start"], duration), 2),
                 "end": round(_hold(word["end"], duration), 2),
                 "word": clean(word.get("word"))}
                for word in cue["words"]
                if word.get("start") is not None and word.get("end") is not None
                and clean(word.get("word"))
            ]
        kept.append(make(start, end, text, words))
    return kept


# --------------------------------------------------------------------------
#  Writers
# --------------------------------------------------------------------------

def to_srt(cues):
    """SubRip. One numbered block per cue, a blank line between blocks."""
    blocks = []
    for index, cue in enumerate(cues, start=1):
        blocks.append("%d\n%s --> %s\n%s\n"
                      % (index, clock(cue["start"]), clock(cue["end"]), cue["text"]))
    return "\n".join(blocks)


def to_vtt(cues):
    """WebVTT. The same timings as SRT with a dot before the milliseconds."""
    body = "\n\n".join(
        "%s --> %s\n%s" % (clock(cue["start"], VTT_SEPARATOR),
                           clock(cue["end"], VTT_SEPARATOR), cue["text"])
        for cue in cues
    )
    return "WEBVTT\n\n" + body + "\n"


def to_txt(cues):
    """A readable transcript, one line per cue: [HH:MM:SS - HH:MM:SS] text."""
    return "".join(
        "[%s - %s] %s\n" % (short_clock(cue["start"]), short_clock(cue["end"]), cue["text"])
        for cue in cues
    )


def to_json(cues):
    """The machine readable form. Non ASCII is kept as it is, not escaped."""
    return json.dumps(cues, ensure_ascii=False, indent=2) + "\n"


WRITERS = {"srt": to_srt, "vtt": to_vtt, "txt": to_txt, "json": to_json}


def write(path, cues, kind=None):
    """Write cues to path. The format comes from the extension unless given."""
    if kind is None:
        kind = path.rsplit(".", 1)[-1].lower()
    if kind not in WRITERS:
        raise ValueError("Unknown caption format %r. Use one of: %s"
                         % (kind, ", ".join(sorted(WRITERS))))
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(WRITERS[kind](cues))
    return path


def srt_from_starts(starts, total, label=None):
    """Build SRT text from bare start times, each cue ending where the next begins.

    That is the shape the renderer consumes, and it is what the fixtures and the
    setup check need, so the format lives here instead of being written out by
    hand in three separate places.
    """
    ends = list(starts[1:]) + [total]
    if label is None:
        label = lambda index: "Line %d" % (index + 1)  # noqa: E731
    cues = [make(start, end, label(index))
            for index, (start, end) in enumerate(zip(starts, ends))]
    return to_srt(cues)


# --------------------------------------------------------------------------
#  Re-splitting
# --------------------------------------------------------------------------

def _pseudo_words(cue):
    """Split a cue into words, timed proportionally when real timings are absent.

    Real word timings are used when the engine produced them. Otherwise each word
    gets a share of the cue proportional to its length, which is close enough for
    choosing a split point and costs nothing to compute.
    """
    if cue.get("words"):
        return [dict(word) for word in cue["words"]]
    pieces = cue["text"].split()
    if not pieces:
        return []
    weights = [len(piece) + 1 for piece in pieces]
    total = float(sum(weights))
    span = cue["end"] - cue["start"]
    words = []
    position = cue["start"]
    for piece, weight in zip(pieces, weights):
        length = span * (weight / total)
        words.append({"start": position, "end": position + length, "word": piece})
        position += length
    words[-1]["end"] = cue["end"]
    return words


def _group(words, max_chars, max_seconds, target_chars=0.0, target_seconds=0.0, cap=0):
    """Pack words into groups, never exceeding the hard limits.

    The limits are absolute. The targets only nudge towards equal sized groups
    and are ignored once `cap` groups exist, so aiming for balance can never add
    a group that the limits did not already require.
    """
    groups = []
    current = []
    used = 0
    for word in words:
        if current:
            piece = word["word"]
            joined = used + 1 + len(piece)
            span = word["end"] - current[0]["start"]
            over = (max_chars > 0 and joined > max_chars) or \
                   (max_seconds > 0 and span > max_seconds)
            if not over and (cap == 0 or len(groups) < cap - 1):
                over = (target_chars > 0 and used >= target_chars) or \
                       (target_seconds > 0 and
                        (current[-1]["end"] - current[0]["start"]) >= target_seconds)
            if over:
                groups.append(current)
                current = []
                used = 0
        used = used + 1 + len(word["word"]) if current else len(word["word"])
        current.append(word)
    if current:
        groups.append(current)
    return groups


def _split_one(cue, max_chars, max_seconds):
    """Split one cue into as few balanced pieces as the limits allow."""
    text = cue["text"]
    duration = cue["end"] - cue["start"]
    if (max_chars <= 0 or len(text) <= max_chars) and \
       (max_seconds <= 0 or duration <= max_seconds):
        return [dict(cue)]

    words = _pseudo_words(cue)
    if len(words) < 2:
        # A single word longer than the limit cannot be split any further.
        return [dict(cue)]

    # First pass: how many groups do the limits actually force? Word boundaries
    # rarely divide evenly, so this is measured rather than derived from a ceil.
    count = max(1, len(_group(words, max_chars, max_seconds)))
    # Second pass: same limits, but aim for equal sized groups so the last one is
    # not left as a stub.
    groups = _group(
        words, max_chars, max_seconds,
        target_chars=len(text) / float(count) if max_chars > 0 else 0.0,
        target_seconds=duration / float(count) if max_seconds > 0 and max_chars <= 0 else 0.0,
        cap=count,
    )

    out = [make(group[0]["start"], group[-1]["end"],
                " ".join(word["word"] for word in group),
                group if cue.get("words") else None)
           for group in groups]
    # Splitting must never move the outer edges of the original cue.
    out[0]["start"] = cue["start"]
    out[-1]["end"] = cue["end"]
    return out


def _merge_short(cues, min_seconds):
    """Fold cues shorter than min_seconds into their neighbour.

    A cue too short to register as an image is worse than a slightly long one, so
    these are absorbed rather than dropped, which keeps every word.
    """
    out = []
    for cue in cues:
        if out and (cue["end"] - cue["start"]) < min_seconds:
            previous = out[-1]
            previous["end"] = cue["end"]
            previous["text"] = clean(previous["text"] + " " + cue["text"])
            if previous.get("words") and cue.get("words"):
                previous["words"] = previous["words"] + cue["words"]
            continue
        out.append(dict(cue))
    # The first cue has no neighbour behind it, so it absorbs the one in front.
    while len(out) > 1 and (out[0]["end"] - out[0]["start"]) < min_seconds:
        first, second = out[0], out[1]
        second["start"] = first["start"]
        second["text"] = clean(first["text"] + " " + second["text"])
        if first.get("words") and second.get("words"):
            second["words"] = first["words"] + second["words"]
        out.pop(0)
    return out


def resplit(cues, max_chars=0, max_seconds=0.0, min_seconds=0.0):
    """Reshape cues to the requested limits without losing or reordering a word.

    Short cues are merged first, then long ones are split. The other way round
    would split a cue and immediately merge the pieces back together.

    A piece produced by an explicit max may still come out under min_seconds. The
    max wins, because it is the one the image count depends on.
    """
    if not cues:
        return []
    out = [dict(cue) for cue in cues]
    if min_seconds > 0:
        out = _merge_short(out, min_seconds)
    if max_chars > 0 or max_seconds > 0:
        split = []
        for cue in out:
            split.extend(_split_one(cue, max_chars, max_seconds))
        out = split
    return out
