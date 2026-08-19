r"""Finish the speech engine install: record the interpreter, fetch the model.

Setup.bat calls this once pip has put the packages into runtime\whisper\lib.
It is a script rather than an inline one liner because quoting Python inside a
.bat file is a reliable source of bugs, and this has to get the percent signs in
a version string right.

    python setup_speech.py [base|tiny|small]
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from i2v import speech  # noqa: E402


def main(argv):
    model = argv[0] if argv else speech.DEFAULT_MODEL
    if model not in speech.MODEL_SIZES:
        print("   unknown model %r, using %s instead" % (model, speech.DEFAULT_MODEL))
        model = speech.DEFAULT_MODEL

    lib = speech.lib_dir(ROOT)
    if not os.path.isdir(lib):
        print("   the packages are not in %s" % lib)
        return 1

    # Extension modules are built for one CPython version, so record which one
    # installed them. i2v/speech.py reads this back and asks for a reinstall
    # rather than letting a changed interpreter fail as a bare ImportError.
    with open(os.path.join(lib, speech.VERSION_MARKER), "w", encoding="utf-8") as handle:
        handle.write(speech.python_tag())

    try:
        speech.activate(ROOT)
        import faster_whisper  # noqa: F401,PLC0415
    except Exception as error:  # noqa: BLE001
        print("   the speech engine will not import: %s" % error)
        return 1

    if speech.model_is_local(ROOT, model):
        print("   the %s model is already here, nothing to download" % model)
        return 0

    try:
        speech.download(ROOT, model)
    except speech.SpeechError as error:
        print("   %s" % error)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(130)
