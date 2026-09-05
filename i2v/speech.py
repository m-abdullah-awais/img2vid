r"""Speech to text, using faster-whisper on the CPU.

This is the only module in the project that touches a third party package, and
it does so lazily. `faster_whisper` is imported inside a function, never at
module import time, so `i2v` as a whole still runs on the standard library alone
and the video side keeps working on a machine where transcription was never
installed.

Everything lives inside the project folder, per the project rules:

    runtime\whisper\lib      the packages, installed with pip --target
    runtime\whisper\models   the model weights, in HuggingFace cache layout

Nothing is written to the user profile or anywhere else on the machine.
"""

import hashlib
import json
import os
import sys
import time

# Only the sizes that finish in reasonable time on a CPU. medium and large-v3
# run slower than realtime on a 4 core laptop, which defeats the point.
MODEL_SIZES = ("tiny", "base", "small")
DEFAULT_MODEL = "base"

REPO = "Systran/faster-whisper-%s"

# The one file that proves a download finished. Everything else is small metadata
# that lands long before the weights do.
WEIGHTS = "model.bin"

# Written by Setup.bat next to the installed packages. Extension modules are
# built for one CPython version, so a changed interpreter has to be caught here
# and reported, rather than surfacing as a bare ImportError later on.
VERSION_MARKER = ".python-version"

# How long to wait between download attempts. The last entry is never slept on,
# it only marks the final try, so this is six attempts over about four minutes.
# A rate limit on the Hub is measured in minutes, not seconds: the old schedule
# stopped after 45 of them and told the user to run Setup again, which is the
# same wait with more steps in it.
RETRY_WAITS = (5, 15, 30, 60, 120, 0)

# The Hub often says when to come back, in a Retry-After header, and its own
# number beats any schedule guessed here. It is a value off the network though,
# so it is capped: a large one would look like the run had hung.
LONGEST_WAIT = 300


class SpeechError(RuntimeError):
    """Raised when the speech engine is missing, unusable or fails to transcribe."""


def root_dir(project_root):
    return os.path.join(project_root, "runtime", "whisper")


def lib_dir(project_root):
    return os.path.join(root_dir(project_root), "lib")


def models_dir(project_root):
    return os.path.join(root_dir(project_root), "models")


def python_tag():
    """The interpreter the installed packages have to match."""
    return "%d.%d" % sys.version_info[:2]


def cache_folder_name(model):
    """The folder HuggingFace keeps one model in, which is what a user copies.

    Named once because two places need it: the check for weights already on
    disk, and the message that tells a user which folder to carry over from a
    machine that has them.
    """
    return "models--" + REPO.replace("/", "--") % model


def model_is_local(project_root, model):
    """True when the weights are really on disk, so no network call is needed.

    The presence of the folder is not enough to go on. An interrupted download
    leaves the folder, the metadata and a part file behind, with no model.bin.
    Treating that as complete is worse than not caching at all: the download is
    never resumed, and every later run fails offline with an incomplete snapshot
    instead of simply finishing the job.
    """
    folder = os.path.join(models_dir(project_root), cache_folder_name(model))
    snapshots = os.path.join(folder, "snapshots")
    if not os.path.isdir(snapshots):
        return False
    for name in os.listdir(snapshots):
        weights = os.path.join(snapshots, name, WEIGHTS)
        # isfile follows symlinks, so a dangling link counts as missing.
        if os.path.isfile(weights) and os.path.getsize(weights) > 0:
            return True
    return False


def activate(project_root):
    """Put the private package folder on sys.path and pin every cache inside it.

    Returns the folder. Raises SpeechError if it is missing or was built for a
    different Python.
    """
    lib = lib_dir(project_root)
    if not os.path.isdir(lib):
        raise SpeechError(
            "The speech engine is not installed.\n"
            "  Run Setup.bat to install it into %s" % lib
        )

    marker = os.path.join(lib, VERSION_MARKER)
    if os.path.isfile(marker):
        with open(marker, "r", encoding="utf-8", errors="replace") as handle:
            installed = handle.read().strip()
        if installed and installed != python_tag():
            raise SpeechError(
                "The speech engine was installed for Python %s but this is Python %s.\n"
                "  Run Setup.bat again to reinstall it for this interpreter."
                % (installed, python_tag())
            )

    if lib not in sys.path:
        sys.path.insert(0, lib)

    models = models_dir(project_root)
    os.makedirs(models, exist_ok=True)
    # Set before huggingface_hub is imported anywhere. Xet stalls on some
    # networks, and pointing HF_HOME at the project folder guarantees nothing
    # is cached in the user profile.
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("HF_HOME", models)
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", models)
    return lib


def available(project_root):
    """True when transcription can run right now, without raising."""
    try:
        activate(project_root)
    except SpeechError:
        return False
    try:
        import faster_whisper  # noqa: F401,PLC0415
    except Exception:  # noqa: BLE001 - a broken install must not crash the caller
        return False
    return True


def download(project_root, model=DEFAULT_MODEL, on_message=None):
    """Fetch the weights into the project folder. Safe to re-run."""
    if model not in MODEL_SIZES:
        raise SpeechError("Unknown model %r. Choose one of: %s"
                          % (model, ", ".join(MODEL_SIZES)))
    activate(project_root)
    destination = models_dir(project_root)
    if on_message:
        on_message("  downloading %s into %s" % (REPO % model, destination))
    try:
        from huggingface_hub import snapshot_download  # noqa: PLC0415
    except ImportError as error:
        raise SpeechError("The speech engine is not installed correctly: %s" % error)

    # A 429 from the Hub is a "come back shortly", not a refusal, and a dropped
    # connection part way through a 140 MB download is ordinary. Both are worth
    # waiting out rather than making the user run Setup again. Already finished
    # files are skipped on the retry, so this resumes rather than restarts.
    last = None
    for attempt, pause in enumerate(RETRY_WAITS, start=1):
        try:
            snapshot_download(REPO % model, cache_dir=destination)
            return destination
        except Exception as error:  # noqa: BLE001 - network, disk, anything
            last = error
            if not network_problem(error) or attempt == len(RETRY_WAITS):
                break
            # Never shorter than the schedule, never longer than the cap. The
            # Hub asking for two seconds is not a reason to hammer it.
            wait = max(pause, retry_after(error) or 0)
            if on_message:
                on_message("  %s, waiting %s and trying again (%d of %d)"
                           % (network_problem(error), spelled(wait),
                              attempt, len(RETRY_WAITS) - 1))
            time.sleep(wait)

    problem = network_problem(last)
    if problem:
        raise SpeechError(
            "Could not download the %s model, because %s.\n"
            "  It kept trying for about %s. A limit like this one is on the\n"
            "  network address, not on this folder, and clears on its own.\n"
            "\n"
            "  Run Setup.bat again later. It is a one time download and it\n"
            "  carries on from where it stopped.\n"
            "\n"
            "  Or take the model off a machine that already has it and skip\n"
            "  the download altogether. Copy this whole folder\n"
            "    %s\n"
            "  from that machine into the same place here:\n"
            "    %s"
            % (model, problem, spelled(sum(RETRY_WAITS)),
               cache_folder_name(model), destination))
    raise SpeechError("Could not download %s: %s" % (REPO % model, last))



def retry_after(error):
    """The wait the Hub asked for, in seconds, when it sent one.

    Capped rather than trusted. The header is also allowed to hold an HTTP
    date rather than a count of seconds, which is not worth parsing: the
    schedule in RETRY_WAITS is a reasonable answer either way, and is what
    the caller falls back on when this returns None.
    """
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    try:
        seconds = int(float(str(headers.get("retry-after", "")).strip()))
    except (TypeError, ValueError):
        return None
    return max(0, min(seconds, LONGEST_WAIT))


def spelled(seconds):
    """A wait as a person would say it, so 120 reads as 2m rather than 120s."""
    if seconds < 60:
        return "%ds" % seconds
    minutes, rest = divmod(int(seconds), 60)
    return "%dm" % minutes if not rest else "%dm %ds" % (minutes, rest)


def network_problem(error):
    """Name the network failure behind a HuggingFace error, if that is what it is.

    Returned as something a user can read. Anything else is a real fault and is
    passed through untouched rather than dressed up as a connection problem.
    """
    # The status code when there is one, because it is exact. The text is only
    # a fallback: "429" as a substring could as easily be part of a byte count
    # or a request id as the status of the response.
    status = getattr(getattr(error, "response", None), "status_code", None)
    text = str(error)
    if status == 429 or "429" in text or "Too Many Requests" in text:
        return "huggingface.co is refusing downloads for now (429 Too Many Requests)"
    for sign in ("ConnectionError", "Max retries", "getaddrinfo", "NewConnectionError",
                 "Temporary failure", "timed out", "SSLError", "ProxyError"):
        if sign in text:
            return "huggingface.co could not be reached"
    return None


def load(project_root, model=DEFAULT_MODEL, compute_type="int8", cpu_threads=0):
    """Load a model. A copy already on disk is used without touching the network.

    Offline is tried first every single time, not only when model_is_local()
    believes the weights are there. Asking the Hub whether a cached model is
    still current turns a rate limit or a dropped connection into a failure on
    a machine that already had everything it needed, which is the worst kind of
    outage: avoidable, and nowhere near where the user thinks the fault is.
    """
    if model not in MODEL_SIZES:
        raise SpeechError("Unknown model %r. Choose one of: %s"
                          % (model, ", ".join(MODEL_SIZES)))
    activate(project_root)
    try:
        from faster_whisper import WhisperModel  # noqa: PLC0415
    except ImportError as error:
        raise SpeechError(
            "The speech engine is installed but will not import: %s\n"
            "  Run Setup.bat again to repair it." % error
        )

    settings = {"device": "cpu", "compute_type": compute_type,
                "cpu_threads": cpu_threads, "download_root": models_dir(project_root)}
    try:
        return WhisperModel(model, local_files_only=True, **settings)
    except Exception:  # noqa: BLE001 - simply not on disk yet, so go and fetch it
        pass

    try:
        return WhisperModel(model, local_files_only=False, **settings)
    except Exception as error:  # noqa: BLE001
        problem = network_problem(error)
        if not problem:
            raise SpeechError("Could not load the %s model: %s" % (model, error))
        raise SpeechError(
            "The %s model is not on this machine yet, and %s.\n"
            "\n"
            "  Nothing is wrong with your files. The model is a one time download\n"
            "  and it has not finished here yet.\n"
            "\n"
            "  Either wait a few minutes and run Setup.bat again, which carries on\n"
            "  from where it stopped, or copy this folder from a machine where it\n"
            "  already works:\n"
            "    %s"
            % (model, problem, models_dir(project_root)))


def signature(paths, options):
    """A stable key for a transcription, over the inputs and the settings.

    Path, size and modification time identify the audio without reading it, and
    the settings are included because changing any of them changes the output.
    """
    digest = hashlib.sha1()
    for path in paths:
        digest.update(os.path.abspath(path).encode("utf-8", "replace"))
        try:
            stat = os.stat(path)
            digest.update(("|%d|%d" % (stat.st_size, int(stat.st_mtime))).encode("ascii"))
        except OSError:
            pass
    digest.update(json.dumps(options, sort_keys=True, default=str).encode("utf-8"))
    return digest.hexdigest()


def transcribe(project_root, audio, duration=None, model=DEFAULT_MODEL, language=None,
               beam_size=1, word_timestamps=False, condition=False, batch_size=0,
               compute_type="int8", cpu_threads=0, on_progress=None, on_message=None):
    """Transcribe one audio file into a list of caption cues.

    `duration` is used to report progress and to hold the final timestamps inside
    the audio, because whisper routinely overshoots the end of the last segment.

    `batch_size` above zero uses the batched pipeline, which groups the speech
    regions the voice detector found and decodes several at once.
    """
    from . import captions  # noqa: PLC0415

    engine = load(project_root, model, compute_type, cpu_threads)

    settings = {
        "language": language or None,
        "beam_size": beam_size,
        "word_timestamps": word_timestamps,
        "condition_on_previous_text": condition,
        "vad_filter": True,
    }

    if batch_size > 0:
        try:
            from faster_whisper import BatchedInferencePipeline  # noqa: PLC0415
        except ImportError as error:
            raise SpeechError("Batched decoding is not available in this build: %s" % error)
        runner = BatchedInferencePipeline(model=engine)
        settings["batch_size"] = batch_size
        # The batched pipeline defaults to without_timestamps=True, which makes
        # it emit one cue per speech region the voice detector found. Measured
        # on a 399s narration that is 15 cues instead of 86, which would mean
        # one image every 26 seconds. Sentence level cues are the whole point
        # here, so the timestamps have to be asked for explicitly.
        settings["without_timestamps"] = False
    else:
        runner = engine

    if on_message:
        on_message("  model      : %s (%s, cpu%s)"
                   % (model, compute_type,
                      ", batch %d" % batch_size if batch_size > 0 else ""))

    try:
        segments, info = runner.transcribe(audio, **settings)
    except Exception as error:  # noqa: BLE001
        raise SpeechError("Transcription failed: %s" % error)

    cues = []
    try:
        # The generator is lazy, so this loop is where the decoding actually
        # happens and where progress can be reported.
        for segment in segments:
            if on_progress and duration and segment.end is not None:
                on_progress(min(1.0, max(0.0, float(segment.end) / duration)))
            words = None
            if word_timestamps and getattr(segment, "words", None):
                words = [{"start": word.start, "end": word.end, "word": word.word}
                         for word in segment.words
                         if word.start is not None and word.end is not None]
            cues.append({"start": segment.start, "end": segment.end,
                         "text": segment.text or "", "words": words})
    except Exception as error:  # noqa: BLE001
        # KeyboardInterrupt is not an Exception, so a cancel still propagates.
        raise SpeechError("Transcription failed part way through: %s" % error)

    cues = captions.clamp(cues, duration)
    if not cues:
        raise SpeechError(
            "No speech was found in %s.\n"
            "  Is the file actually narration, rather than silence or music?"
            % os.path.basename(audio)
        )
    if on_progress:
        on_progress(1.0)
    return cues, {"language": getattr(info, "language", None),
                  "language_probability": getattr(info, "language_probability", None)}
