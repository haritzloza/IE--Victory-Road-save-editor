"""Summary page."""

from PySide6.QtWidgets import (
    QFrame, QGridLayout, QLabel, QProgressBar, QScrollArea, QVBoxLayout, QWidget,
)

from ...catalog import CHRONICLE_DIFFICULTY_NAMES
from .. import theme
from ..common import (label, Page, Card)


class SummaryPage(Page):
    def __init__(self, win):
        super().__init__('Resumen', 'Tu partida de un vistazo')
        self.win = win
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        self.grid = QGridLayout(inner)
        self.grid.setSpacing(14)
        self.grid.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(inner)
        self.lay.addWidget(scroll, 1)
        specs = [('time', 'Tiempo de juego', theme.ACCENT), ('players', 'Jugadores', theme.TEXT),
                 ('items', 'Objetos y equipamiento', theme.TEXT), ('tech', 'Supertécnicas', theme.ACCENT),
                 ('keshin', 'Keshins', '#a35cff'), ('armor', 'Armaduras keshin', '#3d8bff'),
                 ('normal', 'Espíritus normales', theme.TIER_COLORS[0]), ('hero', 'Espíritus héroe', '#ff6fb5'),
                 ('basara', 'Espíritus basara', '#ffb347')]
        self.cards = {}
        for i, (key, title, color) in enumerate(specs):
            c = Card(title, color)
            self.cards[key] = c
            self.grid.addWidget(c, i // 3, i % 3)
        chron = QFrame()
        chron.setObjectName('Card')
        cl = QVBoxLayout(chron)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(10)
        cl.addWidget(label('Crónica · partidos superados por dificultad', 'CardLabel'))
        self.chron_rows = []
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(10)
        for i, n in enumerate(CHRONICLE_DIFFICULTY_NAMES):
            name, bar, num = QLabel(n), QProgressBar(), label('', 'CardLabel')
            name.setStyleSheet('background: transparent;')
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setStyleSheet(f'QProgressBar::chunk {{ background: {theme.SUCCESS}; border-radius: 4px; }}')
            g.addWidget(name, i, 0)
            g.addWidget(bar, i, 1)
            g.addWidget(num, i, 2)
            self.chron_rows.append((bar, num))
        g.setColumnStretch(1, 1)
        cl.addLayout(g)
        self.grid.addWidget(chron, 3, 0, 1, 3)
        self.grid.setRowStretch(4, 1)

    def refresh(self):
        st = self.win.state
        cat = st.cat
        info = st.info()
        t = info.get('time', 0)
        try:
            (major, minor), fmt = st.save.versions()
            ver = f'versión {major}.{minor}' + ('  ⚠️ más nueva que la probada' if st.save.newer_than_tested() else '')
        except (KeyError, IndexError):
            ver = ''
        self.cards['time'].set(f'{t // 3600} h {t % 3600 // 60:02} min',
                               f"Guardado el {info.get('date', '?')} · {ver}")
        self.cards['players'].set(len(st.players()), 'en tu plantilla')

        def ratio(key, pred):
            items = [it for it in cat.items.values() if pred(it)]
            have = sum(1 for it in items if st.owned.get(it.id, 0))
            self.cards[key].set(f'{have} / {len(items)}', f'{have * 100 // max(len(items), 1)} % del catálogo',
                                have, len(items))
        ratio('items', lambda it: it.category != 'SPECIAL_SKILL')
        ratio('tech', lambda it: it.kind.startswith('Supertécnica'))
        ratio('keshin', lambda it: it.kind == 'Keshin')
        ratio('armor', lambda it: it.kind == 'Armadura Keshin')
        for kind in ('normal', 'hero', 'basara'):
            total = [s for s in cat.spirits.values() if s.kind == kind]
            have = sum(1 for s in total if st.spirit_owned(s))
            self.cards[kind].set(f'{have} / {len(total)}', f'{have * 100 // max(len(total), 1)} % del catálogo',
                                 have, len(total))
        n = len(cat.chronicle)
        for k, (bar, num) in enumerate(self.chron_rows, 1):
            c = sum(1 for m in cat.chronicle if st.editor.chronicle_cleared(m.flag_index) >= k)
            bar.setRange(0, n)
            bar.setValue(c)
            num.setText(f'{c} / {n}')
