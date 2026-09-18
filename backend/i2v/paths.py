r"""Every folder the project uses, worked out once.

The project folder is the one that holds backend\ and frontend\. Everything the
app installs or makes lives inside backend\, so the project folder itself holds
only what a person clicks or reads:

    backend\runtime\     private Python, ffmpeg, Node and the speech engine,
                         all put there by Setup.bat and all gitignored
    backend\storage\     every project, its uploads and its videos, plus the
                         engine's working files, also gitignored

Nothing is written to the user profile or anywhere else on the machine.
"""

import os

# IMAGE_EXTENSIONS is re-exported so there is one list of image types, the
# renderer's, rather than a second copy that could drift from it.
from .render import IMAGE_EXTENSIONS, natural_key  # noqa: F401

# This file is backend\i2v\paths.py, so the project folder is three up.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, "backend")
FRONTEND = os.path.join(ROOT, "frontend")

RUNTIME = os.path.join(BACKEND, "runtime")
BIN = os.path.join(RUNTIME, "bin")

STORAGE = os.path.join(BACKEND, "storage")
PROJECTS = os.path.join(STORAGE, "projects")
# Job folders, the encoder choice, the transcription cache, rename records and
# thumbnails. Anything in here can be deleted and is made again when needed.
WORK = os.path.join(STORAGE, "work")
TRASH = os.path.join(STORAGE, "trash")

# In preference order. After transcribing there is a readable .txt next to the
# .srt, so the first extension present wins rather than whichever sorts first.
TRANSCRIPT_EXTENSIONS = (".srt", ".vtt", ".txt")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma")


def listing(folder, extensions):
    """Files in a folder with the given extensions, in natural filename order."""
    if not os.path.isdir(folder):
        return []
    names = [
        name for name in os.listdir(folder)
        if name.lower().endswith(extensions)
        and os.path.isfile(os.path.join(folder, name))
    ]
    names.sort(key=natural_key)
    return [os.path.join(folder, name) for name in names]
