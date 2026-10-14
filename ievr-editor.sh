#!/bin/sh
# Lanza el editor; crea el entorno virtual la primera vez.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt || exit 1
fi
exec .venv/bin/python -m ievr_editor "$@"
