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


def model_is_local(project_root, model):
    """True when the weights are really on disk, so no network call is needed.

    The presence of the folder is not enough to go on. An interrupted download
    leaves the folder, the metadata and a part file behind, with no model.bin.
    Treating that as complete is worse than not caching at all: the download is
    never resumed, and every later run fails offline with an incomplete snapshot
    instead of simply finishing the job.
    """
    folder = os.path.join(models_dir(project_root),
                          "models--" + REPO.replace("/", "--") % model)
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
    try:
        snapshot_download(REPO % model, cache_dir=destination)
    except Exception as error:  # noqa: BLE001 - network, disk, anything
        raise SpeechError("Could not download %s: %s" % (REPO % model, error))
    return destination


def load(project_root, model=DEFAULT_MODEL, compute_type="int8", cpu_threads=0):
    """Load a model, preferring the local copy so a normal run never hits the network."""
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
    try:
        return WhisperModel(
            model,
            device="cpu",
            compute_type=compute_type,
            cpu_threads=cpu_threads,
            download_root=models_dir(project_root),
            local_files_only=model_is_local(project_root, model),
        )
    except Exception as error:  # noqa: BLE001
        raise SpeechError("Could not load the %s model: %s" % (model, error))


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
