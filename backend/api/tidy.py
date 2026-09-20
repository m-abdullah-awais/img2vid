r"""Clear out files older copies of the app left in projects, once, at startup.

Everything is done in the browser now, so a project should hold only what the
user put there and what the app really reads. The transcription step used to
write three files beside each other:

    script.srt      the transcript the renderer reads, and the one kept
    script.txt      the same cues as readable text
    script.json     the same cues again, "for any other tool"

Nothing here reads either of the last two. The transcript in use is chosen in
the order .srt, .vtt, .txt, so a text copy beside an SRT is never the one used,
and a download makes the text from the SRT on demand. The app now asks the
script for the SRT alone; this clears what earlier runs left behind.

A .json is deleted outright: it can only have been written by the transcription
step, since a .json cannot be uploaded as a transcript. A .txt goes to the trash
instead, because in principle it could be one the user uploaded before
transcribing, and the trash can be undone.
"""

import os

from . import projects, trash

DERIVED = ".json"
# Only ever removed when one of these holds the real transcript.
PREFERRED = (".srt", ".vtt")


def transcript_leftovers(folder):
    """(json files, text files) that are no longer the transcript in use."""
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return [], []
    extensions = {os.path.splitext(name)[1].lower() for name in names}
    if not extensions & set(PREFERRED):
        return [os.path.join(folder, name) for name in names
                if name.lower().endswith(DERIVED)], []
    leftovers = {".json": [], ".txt": []}
    for name in names:
        extension = os.path.splitext(name)[1].lower()
        if extension in leftovers:
            leftovers[extension].append(os.path.join(folder, name))
    return leftovers[".json"], leftovers[".txt"]


def run(app):
    """Tidy every project. Returns how many files were removed."""
    removed = 0
    for project_id in projects.ids(app):
        try:
            stored = projects.load(app, project_id)
        except Exception:  # noqa: BLE001 - one unreadable project must not stop the sweep
            continue
        folder = projects.folder(app, project_id, "transcript")
        derived, text = transcript_leftovers(folder)
        for path in derived:
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
        if text:
            try:
                trash.remove_files(app, stored, "transcript", text)
                removed += len(text)
            except Exception:  # noqa: BLE001 - a file in use is tidied next time
                pass
    return removed
