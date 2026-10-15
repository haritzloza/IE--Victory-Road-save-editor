"""Welcome page."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QLabel, QPushButton, QVBoxLayout,
)

from ...savefile import USERDATA_NAME
from ..common import Page


class WelcomePage(Page):
    def __init__(self, win):
        super().__init__('No se ha encontrado ninguna partida',
                         'El editor busca en ~/.local/share/Steam/userdata/<cuenta>/2799860/remote/')
        card = QFrame()
        card.setObjectName('Card')
        v = QVBoxLayout(card)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(10)
        for line in ('1. Abre el juego en Steam y guarda la partida al menos una vez.',
                     '2. Cierra el juego y vuelve a abrir el editor.',
                     '3. Si tu partida está en otro sitio, ábrela a mano con el botón de abajo '
                     f'(el archivo se llama «{USERDATA_NAME}»).'):
            l = QLabel(line)
            l.setWordWrap(True)
            l.setStyleSheet('background: transparent;')
            v.addWidget(l)
        b = QPushButton('📂  Abrir partida…')
        b.setObjectName('Primary')
        b.clicked.connect(win.open_dialog)
        v.addWidget(b, 0, Qt.AlignLeft)
        self.lay.addWidget(card)
        self.lay.addStretch()
