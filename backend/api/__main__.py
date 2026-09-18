r"""Run the img2vid API until Ctrl+C.

    python backend\api --port 8765
    python backend\api --port 8765 --storage temp\some_folder

With the default storage it also imports the files left in the old input and
output folders, once, on startup. Giving --storage turns that off, and so does
--no-import.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
for folder in (os.path.join(BACKEND, "cli"), BACKEND):
    if folder not in sys.path:
        sys.path.insert(0, folder)

from api import server as api_server  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(prog="api", description="The img2vid HTTP API.")
    parser.add_argument("--port", type=int, default=8765, help="port on 127.0.0.1")
    parser.add_argument("--storage", default=None,
                        help="where projects and working files live, default backend\\storage")
    parser.add_argument("--no-import", action="store_true",
                        help="do not import the old input and output folders")
    args = parser.parse_args(argv)

    legacy = None if args.no_import else api_server.AUTO
    running = api_server.serve(port=args.port, storage=args.storage, legacy_root=legacy)
    print("img2vid API listening on %s  (Ctrl+C stops it)" % running.url, flush=True)
    if running.app.imported:
        print("imported the old input and output folders as project %s" % running.app.imported,
              flush=True)
    try:
        while running.thread.is_alive():
            running.thread.join(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        running.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
