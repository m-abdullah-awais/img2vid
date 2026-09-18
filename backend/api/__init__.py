r"""The img2vid HTTP API, a local server over the engine in backend\i2v.

Standard library only, like the video side of the engine. Start it with

    python backend\api --port 8765

or from Python, which is how the launcher runs it:

    from api import server
    running = server.serve(port=8765)
    ...
    running.stop()

Every route, shape and error code follows temp\api-contract.md, which the web
app in frontend\ is written against as well.

Importing this package puts backend\ and backend\cli\ on sys.path, because the
routes call into the engine (i2v) and into the rename script's functions
directly rather than through a subprocess.
"""

import os
import sys

VERSION = "1.0.0"

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
CLI = os.path.join(BACKEND, "cli")

# CLI first and BACKEND in front of it, so i2v always resolves to the package.
for _folder in (CLI, BACKEND):
    if _folder not in sys.path:
        sys.path.insert(0, _folder)
