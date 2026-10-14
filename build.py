"""Build the single-file executable with PyInstaller (Linux and Windows)."""
import os
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent
name = 'ievr-save-editor'
args = [
    str(ROOT / 'run_editor.py'), '--noconfirm', '--clean', '--onefile', '--windowed', '--name', name,
    '--add-data', f'{ROOT / "ievr_editor" / "data"}{os.pathsep}ievr_editor/data',
    '--distpath', str(ROOT / 'dist'), '--workpath', str(ROOT / 'build' / 'pyinstaller'),
    '--specpath', str(ROOT / 'build'),
]
for mod in ('tkinter', 'PySide6.QtNetwork', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtWebEngineCore',
            'PySide6.Qt3DCore', 'PySide6.QtMultimedia', 'PySide6.QtPdf'):
    args += ['--exclude-module', mod]
if sys.platform == 'win32':
    from PIL import Image  # .exe icon must be .ico
    ico = ROOT / 'build' / 'icon.ico'
    ico.parent.mkdir(exist_ok=True)
    Image.open(ROOT / 'ievr_editor' / 'data' / 'icon.png').save(ico, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    args += ['--icon', str(ico)]
PyInstaller.__main__.run(args)
print('Listo:', ROOT / 'dist' / (name + ('.exe' if sys.platform == 'win32' else '')))
