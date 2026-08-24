#!/usr/bin/env python3
r"""img2vid entry point.

Usage:
    python app\img2vid.py -t script.srt -i .\images -a narration.mp3 -o video.mp4
"""

import os
import sys

# This file lives in app\, and the i2v package sits in the project folder
# above it.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from i2v.cli import run

if __name__ == "__main__":
    run()
