#!/bin/sh
# Compila el ejecutable de un solo archivo en dist/ievr-save-editor.
set -e
cd "$(dirname "$(readlink -f "$0")")"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt
fi
.venv/bin/python build.py
