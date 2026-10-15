"""Application entry point: locate the game and the save, build the catalog, show the window."""
import locale
import os
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QInputDialog, QMessageBox,
)

from .. import catalog as catalog_mod
from .. import config
from ..gamedata import GameData, find_game_dir, is_game_dir
from ..icons import IconStore
from ..savefile import USERDATA_NAME, describe_save_dir, find_save_dirs
from . import theme
from .iconloader import IconLoader
from .window import MainWindow, Splash
from ..i18n import tr


def pick_game_dir():
    """Ask for the game folder until a valid one is chosen; remembered in the config."""
    msg = tr('GAME_NOT_FOUND')
    QMessageBox.information(None, tr('Juego no encontrado'), msg)
    while True:
        d = QFileDialog.getExistingDirectory(None, tr('Carpeta de INAZUMA ELEVEN Victory Road'), str(Path.home()))
        if not d:
            return None
        if is_game_dir(d):
            config.set('game_dir', d)
            return d
        QMessageBox.warning(None, tr('Carpeta incorrecta'),
                            tr('«{path}» no parece la carpeta del juego (falta data/cpk_list.cfg.bin).', path=d))


def text_language(gd):
    """Language of item/character names: config, then system locale, then English/Spanish."""
    langs = gd.languages()
    pref = config.get('language') or locale.getlocale()[0] or os.environ.get('LANG', '')
    pref = (pref or '').split('_')[0].split('.')[0].lower()
    for cand in (pref, 'es', 'en'):
        if cand in langs:
            return cand
    return langs[0] if langs else 'en'


def choose_save(parent=None):
    """Path of the save to open: the only one, or let the user pick between Steam accounts."""
    dirs = find_save_dirs()
    if not dirs:
        return None
    if len(dirs) == 1:
        return dirs[0] / USERDATA_NAME
    labels = [describe_save_dir(d) for d in dirs]
    last = config.get('last_save_dir')
    current = next((i for i, d in enumerate(dirs) if str(d) == last), 0)
    choice, ok = QInputDialog.getItem(parent, tr('Elegir partida'), tr('Hay varias cuentas de Steam con partida:'),
                                      labels, current, False)
    if not ok:
        return None
    d = dirs[labels.index(choice)]
    config.set('last_save_dir', str(d))
    return d / USERDATA_NAME


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('IEVR Save Editor')
    app.setDesktopFileName('ievr-save-editor')
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent.parent / 'data' / 'icon.png')))
    theme.apply(app)
    game_dir = find_game_dir() or pick_game_dir()
    if not game_dir:
        return 1
    splash = Splash()
    splash.show()
    app.processEvents()
    try:
        gd = GameData(game_dir)
        cat = catalog_mod.build(gd, text_language(gd))
    except Exception as e:  # unexpected game data (new game version, broken install…)
        splash.close()
        QMessageBox.critical(None, tr('Error leyendo el juego'),
                             tr('GAME_READ_ERROR', path=game_dir, error=f'{type(e).__name__}: {e}'))
        return 1
    win = MainWindow(cat, IconLoader(IconStore(gd)))
    splash.close()
    win.show()
    path = sys.argv[1] if len(sys.argv) > 1 else choose_save(win)
    if path:
        win.open(path)
    else:
        win.show_welcome()
    return app.exec()
