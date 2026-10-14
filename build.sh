#!/bin/sh
# Compila el ejecutable de un solo archivo en dist/ievr-save-editor.
set -e
cd "$(dirname "$(readlink -f "$0")")"
R="$PWD"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt pyinstaller
fi
.venv/bin/pyinstaller --noconfirm --clean --onefile --windowed --name ievr-save-editor \
    --add-data "$R/ievr_editor/data:ievr_editor/data" \
    --exclude-module tkinter --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtQml \
    --exclude-module PySide6.QtQuick --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.Qt3DCore \
    --exclude-module PySide6.QtMultimedia --exclude-module PySide6.QtPdf \
    --distpath "$R/dist" --workpath "$R/build/pyinstaller" --specpath "$R/build" "$R/run_editor.py"
echo "Listo: dist/ievr-save-editor"
