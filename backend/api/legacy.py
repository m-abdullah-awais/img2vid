r"""Bringing in the files people kept before there was a web app.

Before the app, a project was one set of folders at the root:

    <root>\input\audio\          the narration
    <root>\input\images\         the images
    <root>\input\script.srt      (or .vtt or .txt) the transcript
    <root>\output\*.mp4          the videos built from them

When the server starts and any of those hold something, it becomes one project,
named after the first audio file, and the files are moved into it. The input
and output folders are removed afterwards only once they are empty, so a file
that was not moved (a note, a helper script, anything that is not media) is
never deleted, and the folder holding it stays.

The root is a parameter so the tests can run this against a fake one. The
server passes the real project folder only when it runs on the default storage.
"""

import os
import shutil
import traceback

from i2v import paths

from . import projects

SCRIPT = "script"


def found(root):
    """Everything worth importing under this root, as {kind: [paths]}."""
    inbox = os.path.join(root, "input")
    return {
        "audio": paths.listing(os.path.join(inbox, "audio"), paths.AUDIO_EXTENSIONS),
        "images": paths.listing(os.path.join(inbox, "images"), paths.IMAGE_EXTENSIONS),
        "transcript": [os.path.join(inbox, SCRIPT + extension)
                       for extension in paths.TRANSCRIPT_EXTENSIONS
                       if os.path.isfile(os.path.join(inbox, SCRIPT + extension))],
        "videos": paths.listing(os.path.join(root, "output"), (".mp4",)),
    }


def import_legacy(app, root):
    """Move the old folders' files into a new project. Returns its id, or None."""
    items = found(root)
    if not any(items.values()):
        return None
    name = os.path.splitext(os.path.basename(items["audio"][0]))[0] if items["audio"] \
        else "Imported project"
    project = projects.create(app, name)
    moved = []
    for kind, sources in items.items():
        destination = projects.folder(app, project["id"], kind)
        for source in sources:
            try:
                shutil.move(source, os.path.join(destination, os.path.basename(source)))
                moved.append(os.path.join(destination, os.path.basename(source)))
            except OSError:
                traceback.print_exc()
    _remove_if_empty(os.path.join(root, "input", "audio"))
    _remove_if_empty(os.path.join(root, "input", "images"))
    _remove_if_empty(os.path.join(root, "input"))
    _remove_if_empty(os.path.join(root, "output"))
    projects.touch(app, project["id"])
    for path in moved:
        if path.lower().endswith(paths.IMAGE_EXTENSIONS):
            app.thumbs.enqueue(path)
    return project["id"]


def _remove_if_empty(folder):
    """rmdir, which refuses a folder with anything left in it. That refusal is the point."""
    try:
        os.rmdir(folder)
    except OSError:
        pass
