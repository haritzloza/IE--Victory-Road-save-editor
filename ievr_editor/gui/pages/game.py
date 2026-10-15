"""Game page: avatar, token spirits, character database and backups."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QVBoxLayout,
)

from ... import config, i18n, paths
from ...i18n import LANGUAGES
from .. import theme
from ...players import Squad
from ...savefile import list_backups, restore_backup
from ..common import Page, game_running, label, undoable
from ...i18n import tr


class GamePage(Page):
    """Avatar name, token spirits and character database."""

    def __init__(self, win):
        super().__init__(tr('Partida'), tr('Avatar, fichas, base de datos de personajes y copias de seguridad'))
        self.win = win
        self.squad = Squad(win.state.editor)
        st = win.state
        info = st.info()
        self.old_name = info.get('name', '')

        avatar = QFrame()
        avatar.setObjectName('Card')
        f = QFormLayout(avatar)
        f.setContentsMargins(20, 18, 20, 18)
        f.setHorizontalSpacing(16)
        f.addRow(label('AVATAR', 'CardLabel'))
        self.name = QLineEdit(self.old_name)
        self.nick = QLineEdit(info.get('nick', ''))
        for w in (self.name, self.nick):
            w.setMaxLength(15)
        f.addRow(tr('Nombre'), self.name)
        f.addRow(tr('Apodo (dorsal)'), self.nick)
        b = QPushButton(tr('Cambiar nombre'))
        b.setObjectName('Primary')
        b.clicked.connect(self.rename)
        f.addRow('', b)

        tokens = QFrame()
        tokens.setObjectName('Card')
        f2 = QFormLayout(tokens)
        f2.setContentsMargins(20, 18, 20, 18)
        f2.addRow(label(tr('ESPÍRITUS FICHA'), 'CardLabel'))
        self.tokens = QSpinBox()
        self.tokens.setRange(0, 99999)
        self.tokens.setValue(st.editor.token_spirits())
        self.tokens.valueChanged.connect(self.tokens_changed)
        f2.addRow(tr('Cantidad'), self.tokens)
        f2.addRow(label(tr('Las judías de entrenamiento están en Objetos → «Judías de entrenamiento».'), 'CardLabel'))
        f2.addRow(QLabel(''))
        f2.addRow(label(tr('IDIOMA'), 'CardLabel'))
        self.lang = QComboBox()
        for code, name in LANGUAGES.items():
            self.lang.addItem(name, code)
        self.lang.setCurrentIndex(list(LANGUAGES).index(i18n.LANG))
        self.lang.currentIndexChanged.connect(self.language_changed)
        f2.addRow(tr('Idioma de la interfaz'), self.lang)
        self.updates = QCheckBox(tr('Buscar actualizaciones al abrir'))
        self.updates.setChecked(config.get('check_updates', True))
        self.updates.toggled.connect(lambda on: config.set('check_updates', on))
        f2.addRow('', self.updates)

        db = QFrame()
        db.setObjectName('Card')
        v = QVBoxLayout(db)
        v.setContentsMargins(20, 18, 20, 18)
        v.addWidget(label(tr('BASE DE DATOS DE PERSONAJES'), 'CardLabel'))
        self.db_label = QLabel()
        self.db_label.setStyleSheet('background: transparent;')
        self.db_bar = QProgressBar()
        self.db_bar.setTextVisible(False)
        self.db_bar.setFixedHeight(8)
        v.addWidget(self.db_label)
        v.addWidget(self.db_bar)
        b2 = QPushButton(tr('Marcar todos los personajes como conocidos'))
        b2.clicked.connect(self.mark_known)
        v.addWidget(b2)

        backups = QFrame()
        backups.setObjectName('Card')
        bv = QVBoxLayout(backups)
        bv.setContentsMargins(20, 18, 20, 18)
        bv.addWidget(label(tr('COPIAS DE SEGURIDAD'), 'CardLabel'))
        bv.addWidget(label(tr('Se crean al guardar y al restaurar, en {path}', path=paths.backup_dir()), 'CardLabel'))
        self.backup_list = QListWidget()
        self.backup_list.setStyleSheet('QListWidget { background: transparent; border: none; } '
                                       'QListWidget::item { padding: 6px; border-radius: 6px; }')
        self.backup_list.setMinimumHeight(150)
        bv.addWidget(self.backup_list, 1)
        b3 = QPushButton(tr('↺  Restaurar la copia seleccionada'))
        b3.clicked.connect(self.restore)
        bv.addWidget(b3, 0, Qt.AlignLeft)

        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(avatar, 1)
        row.addWidget(tokens, 1)
        self.lay.addLayout(row)
        self.lay.addWidget(db)
        self.lay.addWidget(backups, 1)

    def refresh(self):
        self.tokens.blockSignals(True)
        self.tokens.setValue(self.win.state.editor.token_spirits())
        self.tokens.blockSignals(False)
        info = self.win.state.info()
        if info.get('name'):
            self.old_name = info['name']
            self.name.setText(info['name'])
            self.nick.setText(info.get('nick', ''))
            self.win.update_player_label()
        self.backup_list.clear()
        for path, when, size in list_backups(self.win.state.save.path.name):
            it = QListWidgetItem(f'🗂  {when}   ·   {size / 1048576:.1f} MB')
            it.setData(Qt.UserRole, str(path))
            self.backup_list.addItem(it)
        if not self.backup_list.count():
            self.backup_list.addItem(tr('Todavía no hay copias: se crea una cada vez que guardas.'))
        idx = set(self.win.state.cat.chara_flag_index.values())
        known = self.win.state.editor.known_characters(idx)
        self.db_label.setText(tr('{known} de {total} personajes conocidos', known=known, total=len(idx)))
        self.db_bar.setRange(0, len(idx))
        self.db_bar.setValue(known)

    def language_changed(self, _):
        config.set('ui_language', self.lang.currentData())
        self.win.toast.show_message(tr('Se aplicará la próxima vez que abras el editor.'), theme.ACCENT)

    def restore(self):
        it = self.backup_list.currentItem()
        path = it.data(Qt.UserRole) if it else None
        if not path:
            return
        if game_running():
            QMessageBox.warning(self, tr('Juego abierto'), tr('Cierra INAZUMA ELEVEN Victory Road antes de restaurar.'))
            return
        msg = tr('¿Restaurar la partida del {date}?\n\nLa partida actual se guardará antes como copia de seguridad.',
                 date=it.text().split('·')[0][3:].strip())
        if self.win.state.dirty:
            msg += tr('\nLos cambios sin guardar del editor se perderán.')
        if QMessageBox.question(self, tr('Restaurar copia'), msg) != QMessageBox.Yes:
            return
        target = self.win.state.save.path
        try:
            restore_backup(Path(path), target)
        except Exception as e:
            QMessageBox.critical(self, tr('Error'), tr('No se pudo restaurar la copia:\n{error}', error=e))
            return
        self.win.state.journal.mark_saved()  # the reopened save replaces any unsaved edits
        self.win.open(target)
        self.win.go(6)
        self.win.toast.show_message(tr('✔  Copia restaurada'))

    @undoable(lambda self: tr('Renombrar avatar → {name}', name=self.name.text().strip()))
    def rename(self):
        name, nick = self.name.text().strip(), self.nick.text().strip()
        if not name or not self.old_name:
            return
        self.squad.rename(self.old_name, name, nick or name)
        self.old_name = name
        self.win.mark_dirty()
        self.win.update_player_label()
        self.win.toast.show_message(tr('Avatar renombrado a {name}', name=name))

    @undoable(lambda self, n: tr('Espíritus ficha → {n}', n=n))
    def tokens_changed(self, n):
        self.win.state.editor.set_token_spirits(n)
        self.win.mark_dirty()

    @undoable(tr('Marcar todos los personajes como conocidos'))
    def mark_known(self):
        self.win.state.editor.mark_characters_known(set(self.win.state.cat.chara_flag_index.values()))
        self.win.mark_dirty()
        self.refresh()
        self.win.toast.show_message(tr('Todos los personajes marcados como conocidos'))
