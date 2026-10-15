"""Main window: sidebar navigation, page stack, save/open."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from .. import config, paths
from ..savefile import USERDATA_NAME, SaveFile, find_save_dirs
from .common import (game_running, State, label, Toast)
from .pages.items import ItemsPage
from .pages.spirits import SpiritsPage
from .pages.chronicle import ChroniclePage
from .pages.players import PlayersPage
from .pages.game import GamePage
from .pages.summary import SummaryPage
from .pages.welcome import WelcomePage


# ------------------------------------------------------------------------- window

NAV = ['🏠  Resumen', '⚽  Jugadores', '🎒  Objetos', '🔥  Técnicas', '✨  Espíritus', '📜  Crónica', '👤  Partida']


class MainWindow(QMainWindow):
    def __init__(self, cat, icons=None):
        super().__init__()
        self.cat = cat
        self.icons = icons
        self.state = None
        self.setWindowTitle('IEVR Save Editor')
        self.resize(1360, 860)

        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QFrame()
        side.setObjectName('Sidebar')
        side.setFixedWidth(250)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 16)
        sl.setSpacing(2)
        sl.addWidget(label('⚡ Victory Road', 'Brand'))
        sl.addWidget(label('Save Editor', 'BrandSub'))
        self.nav = QButtonGroup(self)
        self.nav_buttons = []
        for i, text in enumerate(NAV):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=i: self.go(i))
            self.nav.addButton(b)
            self.nav_buttons.append(b)
            sl.addWidget(b)
        sl.addStretch()
        self.player = label('', 'BrandSub')
        self.player.setWordWrap(True)
        sl.addWidget(self.player)
        box = QVBoxLayout()
        box.setContentsMargins(14, 0, 14, 0)
        box.setSpacing(8)
        self.save_btn = QPushButton('💾  Guardar cambios')
        self.save_btn.setObjectName('Primary')
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self.do_save)
        open_btn = QPushButton('📂  Abrir otra partida…')
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(self.open_dialog)
        box.addWidget(self.save_btn)
        box.addWidget(open_btn)
        sl.addLayout(box)
        h.addWidget(side)

        self.stack = QStackedWidget()
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.toast = Toast(self)
        QShortcut(QKeySequence.Save, self, self.do_save)
        QShortcut(QKeySequence.Open, self, self.open_dialog)
        QShortcut(QKeySequence.Find, self, self.focus_search)
        for i in range(len(NAV)):
            QShortcut(QKeySequence(f'Ctrl+{i + 1}'), self, lambda i=i: self.go(i))
        self.update_title()

    def go(self, i):
        if not self.state:
            return
        self.nav_buttons[i].setChecked(True)
        self.stack.setCurrentIndex(i)
        self.stack.currentWidget().refresh()

    def focus_search(self):
        w = self.stack.currentWidget()
        if hasattr(w, 'search'):
            w.search.setFocus()
            w.search.selectAll()

    def open(self, path):
        try:
            save = SaveFile(path)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'No se pudo abrir el guardado:\n{e}')
            return
        self.state = State(save, self.cat)
        config.set('last_save_dir', str(Path(path).resolve().parent))
        for b in self.nav_buttons:
            b.setEnabled(True)
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        for page in (SummaryPage(self), PlayersPage(self), ItemsPage(self), ItemsPage(self, skills=True),
                     SpiritsPage(self), ChroniclePage(self), GamePage(self)):
            self.stack.addWidget(page)
        self.path = path
        self.update_player_label()
        self.update_title()
        self.go(0)

    def update_player_label(self):
        info = self.state.info()
        who = f"{info.get('name', '')} «{info.get('nick', '')}»\n" if info.get('name') else ''
        self.player.setText(f'{who}{Path(self.path).name}')

    def show_welcome(self):
        self.stack.addWidget(WelcomePage(self))
        for b in self.nav_buttons:
            b.setEnabled(False)

    def open_dialog(self):
        if not self.confirm_discard():
            return
        dirs = find_save_dirs()
        start = str(dirs[0]) if dirs else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, 'Abrir guardado', start, f'Guardado ({USERDATA_NAME});;Todos (*)')
        if path:
            self.open(path)

    def mark_dirty(self):
        if self.state:
            self.state.dirty = True
        self.update_title()

    def update_title(self):
        dirty = bool(self.state and self.state.dirty)
        self.setWindowTitle(('● ' if dirty else '') + 'IEVR Save Editor')
        self.save_btn.setText('💾  Guardar cambios' + ('  ●' if dirty else ''))
        self.save_btn.setEnabled(dirty)

    def do_save(self):
        if not self.state or not self.state.dirty:
            return
        if game_running():
            QMessageBox.warning(self, 'Juego abierto', 'INAZUMA ELEVEN Victory Road está en ejecución.\n'
                                                       'Ciérralo antes de guardar, o sobrescribirá los cambios.')
            return
        try:
            self.state.save.save()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'No se pudo guardar:\n{e}')
            return
        self.state.dirty = False
        self.update_title()
        self.toast.show_message(f'✔  Guardado · copia del anterior en {paths.backup_dir()}')

    def confirm_discard(self):
        if not self.state or not self.state.dirty:
            return True
        return QMessageBox.question(self, 'Cambios sin guardar', '¿Descartar los cambios sin guardar?') \
            == QMessageBox.Yes

    def closeEvent(self, ev):
        ev.accept() if self.confirm_discard() else ev.ignore()


class Splash(QFrame):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setObjectName('Card')
        self.setFixedSize(440, 150)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.addWidget(label('⚡ Victory Road Save Editor', 'PageTitle'))
        lay.addWidget(label('Leyendo los datos del juego…', 'PageSub'))
        bar = QProgressBar()
        bar.setRange(0, 0)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        lay.addWidget(bar)
