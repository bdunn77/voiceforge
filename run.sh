#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Run ./install.sh first"; exit 1; }
exec .venv/bin/python app.py
