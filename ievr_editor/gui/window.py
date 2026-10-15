"""Main window: sidebar navigation, page stack, save/open."""
from contextlib import nullcontext
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QDialog, QDialogButtonBox, QFileDialog, QFrame, QHBoxLayout, QListWidget,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from .. import config, paths
from ..savefile import USERDATA_NAME, SaveFile, find_save_dirs
from . import theme
from .common import State, Toast, game_running, label
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
        hist = QHBoxLayout()
        hist.setSpacing(8)
        self.undo_btn = QPushButton('↶  Deshacer')
        self.redo_btn = QPushButton('↷  Rehacer')
        for b, fn in ((self.undo_btn, self.undo), (self.redo_btn, self.redo)):
            b.setStyleSheet('padding: 7px 4px;')
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            hist.addWidget(b)
        box.addLayout(hist)
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
        QShortcut(QKeySequence.Undo, self, self.undo)
        QShortcut(QKeySequence.Redo, self, self.redo)
        QShortcut(QKeySequence('Ctrl+Y'), self, self.redo)
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

    def action(self, label):
        """Context manager grouping edits into one undo step."""
        return self.state.journal.action(label) if self.state else nullcontext()

    def mark_dirty(self):
        self.update_title()

    def update_title(self):
        dirty = bool(self.state and self.state.dirty)
        j = self.state.journal if self.state else None
        self.setWindowTitle(('● ' if dirty else '') + 'IEVR Save Editor')
        self.save_btn.setText('💾  Guardar cambios' + ('  ●' if dirty else ''))
        self.save_btn.setEnabled(dirty)
        self.undo_btn.setEnabled(bool(j and j.undo))
        self.redo_btn.setEnabled(bool(j and j.redo))
        self.undo_btn.setToolTip(f'Deshacer: {j.undo[-1].label}' if j and j.undo else '')
        self.redo_btn.setToolTip(f'Rehacer: {j.redo[-1].label}' if j and j.redo else '')

    def _history(self, step, verb):
        if not self.state:
            return
        # don't undo in the middle of an edit (open spin box / combo)
        focus = QApplication.focusWidget()
        if focus is not None and focus.inherits('QAbstractSpinBox'):
            focus.clearFocus()
        label = step()
        if label is None:
            return
        self.state.reload_owned()
        for i in range(self.stack.count()):
            self.stack.widget(i).refresh()
        self.update_title()
        self.toast.show_message(f'{verb}: {label}', theme.ACCENT)

    def undo(self):
        if self.state:
            self._history(self.state.journal.undo_last, 'Deshecho')

    def redo(self):
        if self.state:
            self._history(self.state.journal.redo_last, 'Rehecho')

    def do_save(self):
        if not self.state or not self.state.dirty:
            return
        if game_running():
            QMessageBox.warning(self, 'Juego abierto', 'INAZUMA ELEVEN Victory Road está en ejecución.\n'
                                                       'Ciérralo antes de guardar, o sobrescribirá los cambios.')
            return
        if not ChangesDialog(self, self.state.journal.pending()).exec():
            return
        try:
            self.state.save.save()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'No se pudo guardar:\n{e}')
            return
        self.state.journal.mark_saved()
        self.update_title()
        self.toast.show_message(f'✔  Guardado · copia del anterior en {paths.backup_dir()}')

    def confirm_discard(self):
        if not self.state or not self.state.dirty:
            return True
        return QMessageBox.question(self, 'Cambios sin guardar', '¿Descartar los cambios sin guardar?') \
            == QMessageBox.Yes

    def closeEvent(self, ev):
        ev.accept() if self.confirm_discard() else ev.ignore()


class ChangesDialog(QDialog):
    """List of the changes about to be written, with Save / Cancel."""

    def __init__(self, parent, labels, limit=60):
        super().__init__(parent)
        self.setWindowTitle('Guardar cambios')
        self.resize(560, 460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(10)
        lay.addWidget(label(f'Se van a guardar {len(labels)} cambio(s)', 'PageTitle'))
        lay.addWidget(label('Antes se hará una copia de seguridad de la partida actual.', 'PageSub'))
        lst = QListWidget()
        lst.setStyleSheet(f'QListWidget {{ background: {theme.SURFACE}; border: 1px solid {theme.BORDER};'
                          f' border-radius: 10px; padding: 6px; }} QListWidget::item {{ padding: 4px; }}')
        lst.addItems(labels[:limit])
        if len(labels) > limit:
            lst.addItem(f'… y {len(labels) - limit} más')
        lay.addWidget(lst, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setObjectName('Primary')
        bb.button(QDialogButtonBox.Save).setText('💾  Guardar')
        bb.button(QDialogButtonBox.Cancel).setText('Cancelar')
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


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
