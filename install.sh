#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Python 3.10-3.12 is required"; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg is required on PATH"; exit 1; }
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements/core.txt
echo "Installed. Run ./run.sh"
