"""Game page."""

from PySide6.QtWidgets import (
    QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
    QSpinBox, QVBoxLayout,
)

from ...players import Squad
from ..common import (label, Page)


class GamePage(Page):
    """Avatar name, token spirits and character database."""

    def __init__(self, win):
        super().__init__('Partida', 'Avatar, fichas y base de datos de personajes')
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
        f.addRow('Nombre', self.name)
        f.addRow('Apodo (dorsal)', self.nick)
        b = QPushButton('Cambiar nombre')
        b.setObjectName('Primary')
        b.clicked.connect(self.rename)
        f.addRow('', b)

        tokens = QFrame()
        tokens.setObjectName('Card')
        f2 = QFormLayout(tokens)
        f2.setContentsMargins(20, 18, 20, 18)
        f2.addRow(label('ESPÍRITUS FICHA', 'CardLabel'))
        self.tokens = QSpinBox()
        self.tokens.setRange(0, 99999)
        self.tokens.setValue(st.editor.token_spirits())
        self.tokens.valueChanged.connect(self.tokens_changed)
        f2.addRow('Cantidad', self.tokens)
        f2.addRow(label('Las judías de entrenamiento están en Objetos → «Judías de entrenamiento».', 'CardLabel'))

        db = QFrame()
        db.setObjectName('Card')
        v = QVBoxLayout(db)
        v.setContentsMargins(20, 18, 20, 18)
        v.addWidget(label('BASE DE DATOS DE PERSONAJES', 'CardLabel'))
        self.db_label = QLabel()
        self.db_label.setStyleSheet('background: transparent;')
        self.db_bar = QProgressBar()
        self.db_bar.setTextVisible(False)
        self.db_bar.setFixedHeight(8)
        v.addWidget(self.db_label)
        v.addWidget(self.db_bar)
        b2 = QPushButton('Marcar todos los personajes como conocidos')
        b2.clicked.connect(self.mark_known)
        v.addWidget(b2)

        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(avatar, 1)
        row.addWidget(tokens, 1)
        self.lay.addLayout(row)
        self.lay.addWidget(db)
        self.lay.addStretch()

    def refresh(self):
        idx = set(self.win.state.cat.chara_flag_index.values())
        known = self.win.state.editor.known_characters(idx)
        self.db_label.setText(f'{known} de {len(idx)} personajes conocidos')
        self.db_bar.setRange(0, len(idx))
        self.db_bar.setValue(known)

    def rename(self):
        name, nick = self.name.text().strip(), self.nick.text().strip()
        if not name or not self.old_name:
            return
        self.squad.rename(self.old_name, name, nick or name)
        self.old_name = name
        self.win.mark_dirty()
        self.win.update_player_label()
        self.win.toast.show_message(f'Avatar renombrado a {name}')

    def tokens_changed(self, n):
        self.win.state.editor.set_token_spirits(n)
        self.win.mark_dirty()

    def mark_known(self):
        self.win.state.editor.mark_characters_known(set(self.win.state.cat.chara_flag_index.values()))
        self.win.mark_dirty()
        self.refresh()
        self.win.toast.show_message('Todos los personajes marcados como conocidos')
