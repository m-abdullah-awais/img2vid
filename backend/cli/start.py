r"""Start img2vid: the engine, the web app and a browser tab. Run.bat calls this.

    python backend\cli\start.py [--dev] [--no-browser] [--port 3000]

Everything runs in this one console. The engine's API serves on
127.0.0.1:8765 from a thread in this process, and the web app is a Node child
of it. Both are bound to this process's Windows job object, so closing the
window stops everything, including any video being built.

The web app is served from a production build, so it sits idle while a video
renders instead of recompiling pages. It is rebuilt only when its sources are
newer than the last build. --dev runs the development server instead, for
working on the frontend.
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

# This file lives in backend\cli\, and the i2v and api packages sit in backend\.
# backend\cli\ itself stays on the path too, as sys.path[0], because the API
# imports rename_images from it.
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from i2v import paths, probe  # noqa: E402

API_HOST = "127.0.0.1"
API_PORT = 8765
WEB_PORT = 3000
# How far to look for a free port when 3000 is taken by something else.
WEB_PORT_RANGE = 20

FRONTEND = paths.FRONTEND
BUILD_ID = os.path.join(FRONTEND, ".next", "BUILD_ID")
# Written once the web app answers, so a second double click can find the tab
# the first one opened instead of starting a second copy.
STATE = os.path.join(paths.WORK, "start.json")

# What a build depends on. Anything here newer than the last build means the
# build is stale.
BUILD_INPUTS = ("src", "public", "package.json", "package-lock.json", "next.config.ts",
                "postcss.config.mjs", "tsconfig.json")


def say(text=""):
    print("  %s" % text if text else "", flush=True)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="start",
        description="Start the img2vid engine and web app, and open it in the browser.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--dev", action="store_true",
                        help="run the web app's development server, for working on it")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open a browser tab")
    parser.add_argument("--port", type=int, default=WEB_PORT,
                        help="the web app's port, the next free one is used if it is taken")
    return parser


# --------------------------------------------------------------------------
# Finding things
# --------------------------------------------------------------------------

def find_node():
    """The private Node that Setup.bat unpacked, otherwise the one on PATH."""
    local = os.path.join(paths.RUNTIME, "node", "node.exe")
    if os.path.isfile(local):
        return local
    return shutil.which("node")


def npm_command(node):
    """How to run npm with the same Node, without going through npm.cmd.

    Calling npm-cli.js through node directly means Ctrl+C and a closed window
    reach npm itself rather than a cmd.exe wrapper around it.
    """
    cli = os.path.join(os.path.dirname(node), "node_modules", "npm", "bin", "npm-cli.js")
    if os.path.isfile(cli):
        return [node, cli]
    found = shutil.which("npm")
    return [found] if found else None


def next_command(node, *args):
    return [node, os.path.join(FRONTEND, "node_modules", "next", "dist", "bin", "next")] + list(args)


def child_environment(node):
    env = dict(os.environ)
    # npm's cache and Next's telemetry both default to the user profile. Rule 7
    # of this project keeps everything inside the project folder.
    env["npm_config_cache"] = os.path.join(paths.RUNTIME, "npm-cache")
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    env["PATH"] = os.path.dirname(node) + os.pathsep + env.get("PATH", "")
    return env


def newest_input():
    newest = 0.0
    for name in BUILD_INPUTS:
        path = os.path.join(FRONTEND, name)
        if os.path.isfile(path):
            newest = max(newest, os.path.getmtime(path))
            continue
        for folder, _, files in os.walk(path):
            for file in files:
                newest = max(newest, os.path.getmtime(os.path.join(folder, file)))
    return newest


def build_is_current():
    return os.path.isfile(BUILD_ID) and os.path.getmtime(BUILD_ID) >= newest_input()


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
        try:
            probe_socket.bind((API_HOST, port))
        except OSError:
            return False
    return True


def answers(url, timeout=1.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status < 500, response.read()
    except OSError:
        return False, b""


def engine_already_running():
    ok, body = answers("http://%s:%d/api/health" % (API_HOST, API_PORT))
    if not ok:
        return False
    try:
        return json.loads(body.decode("utf-8")).get("app") == "img2vid"
    except ValueError:
        return False


# --------------------------------------------------------------------------
# Running things
# --------------------------------------------------------------------------

def run_step(command, env, what):
    """Run npm ci or next build in the foreground, output straight through."""
    result = subprocess.run(command, cwd=FRONTEND, env=env)
    if result.returncode != 0:
        raise SystemExit("\n  %s failed. See the message above." % what)


def relay(process, label):
    """Print a child's output with a prefix, so the two logs can be told apart."""
    for raw in iter(process.stdout.readline, b""):
        line = raw.decode("utf-8", "replace").rstrip()
        if line:
            print("  %s | %s" % (label, line), flush=True)


def start_engine():
    """Serve the API from a thread in this process, and return the server.

    The first start also imports anything left in the input and output folders
    from before the web app, as a project of its own.
    """
    from api import server as api_server  # noqa: PLC0415

    return api_server.serve(host=API_HOST, port=API_PORT)


def open_browser(url):
    """Open the app in the default browser, outside this process's job object.

    Everything this process starts dies with it, which is what stops ffmpeg and
    Node when the window closes. A browser started directly would be one of
    those children, so closing img2vid would close the user's browser too.
    explorer.exe hands the URL to the already running Windows shell and exits,
    and the shell starts the browser as its own child instead.
    """
    if os.name == "nt":
        subprocess.Popen(["explorer.exe", url])
    else:
        webbrowser.open(url)


def wait_for(url, seconds, process=None):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            return False
        if answers(url)[0]:
            return True
        time.sleep(0.25)
    return False


def main(argv=None):
    args = build_parser().parse_args(argv)

    say()
    say("img2vid")
    say("-" * 60)

    if engine_already_running():
        url = None
        try:
            with open(STATE, "r", encoding="utf-8") as handle:
                url = json.load(handle).get("web")
        except (OSError, ValueError):
            pass
        say("img2vid is already running in another window.")
        if url and answers(url)[0]:
            say("opening %s" % url)
            if not args.no_browser:
                open_browser(url)
            return 0
        say("Close that window first, then run this again.")
        return 1

    if not port_free(API_PORT):
        say("Port %d is in use by another program, and img2vid needs it." % API_PORT)
        say("Close that program, or restart Windows, then run this again.")
        return 1

    node = find_node()
    if not node:
        say("Node.js was not found. Run Setup.bat first, it installs a private copy.")
        return 1
    env = child_environment(node)

    # Bound before any child starts, so every one of them dies with this window.
    probe.bind_children_to_this_process()

    if not os.path.isdir(os.path.join(FRONTEND, "node_modules")):
        npm = npm_command(node)
        if not npm:
            say("npm was not found next to Node. Run Setup.bat again.")
            return 1
        say("web app   : installing its packages, once")
        run_step(npm + ["ci", "--no-audit", "--no-fund", "--loglevel=error"], env,
                 "Installing the web app's packages")

    if not args.dev and not build_is_current():
        say("web app   : building it, about a minute, only after it changes")
        run_step(next_command(node, "build"), env, "Building the web app")

    httpd = start_engine()
    say("engine    : http://%s:%d" % (API_HOST, API_PORT))

    port = args.port
    while not port_free(port) and port < args.port + WEB_PORT_RANGE:
        port += 1
    url = "http://%s:%d" % (API_HOST, port)

    web = subprocess.Popen(
        next_command(node, "dev" if args.dev else "start", "-p", str(port), "-H", API_HOST),
        cwd=FRONTEND, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, creationflags=probe.NO_WINDOW)
    threading.Thread(target=relay, args=(web, "web"), daemon=True).start()

    try:
        if not wait_for(url, 120, web):
            say("The web app did not start. See the lines marked web above.")
            return 1
        try:
            os.makedirs(paths.WORK, exist_ok=True)
            with open(STATE, "w", encoding="utf-8") as handle:
                json.dump({"web": url, "pid": os.getpid()}, handle)
        except OSError:
            pass

        say("web app   : %s" % url)
        say()
        say("img2vid is running. Keep this window open while you work.")
        say("Close it, or press Ctrl+C, to stop img2vid.")
        say()
        if not args.no_browser:
            open_browser(url)

        while web.poll() is None:
            time.sleep(0.5)
        say("The web app stopped unexpectedly. See the lines marked web above.")
        return 1
    except KeyboardInterrupt:
        say()
        say("stopping img2vid")
        return 0
    finally:
        if web.poll() is None:
            web.kill()
        try:
            # Also cancels a running job, so no render is left half written.
            httpd.stop()
        except Exception:  # noqa: BLE001 - shutting down, nothing left to report to
            pass
        try:
            os.remove(STATE)
        except OSError:
            pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
