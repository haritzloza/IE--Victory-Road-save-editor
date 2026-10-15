"""Players page."""
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from ...players import (EQUIP_SLOTS, MAX_LEVEL, SKILL_SLOTS, Squad, max_training, set_training, training,
                         training_cap)
from .. import theme
from ..tablemodel import Column
from ..common import (AVATAR_ICON, PLAYER_RARITY, rarity_color, label, TablePage, SearchCombo, item_model, undoable)
from ...i18n import tr


class PlayerPanel(QFrame):
    """Level, rarity, equipment and techniques of the selected player."""

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setObjectName('Card')
        self.setFixedWidth(430)
        self.player = None
        self.loading = False
        cat = page.win.state.cat
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet('background: transparent;')
        inner = QWidget()
        inner.setStyleSheet('background: transparent;')
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(8)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        self.face = QLabel()
        self.face.setFixedSize(96, 96)
        self.face.setAlignment(Qt.AlignCenter)
        self.face.setStyleSheet(f'background: {theme.SURFACE_2}; border-radius: 48px;')
        self.title = label(tr('Selecciona un jugador'), 'PageTitle')
        self.title.setStyleSheet('font-size: 15pt;')
        self.title.setWordWrap(True)
        self.subtitle = label('', 'CardLabel')
        head = QHBoxLayout()
        head.setSpacing(14)
        head.addWidget(self.face)
        names = QVBoxLayout()
        names.addStretch()
        names.addWidget(self.title)
        names.addWidget(self.subtitle)
        names.addStretch()
        head.addLayout(names, 1)
        lay.addLayout(head)
        self.icon_labels = {}
        if page.win.icons is not None:
            page.win.icons.ready.connect(lambda _k: self.refresh_icons())

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        self.level = QSpinBox()
        self.level.setRange(1, MAX_LEVEL)
        self.level.valueChanged.connect(self.level_changed)
        self.rarity = QComboBox()
        for i, n in enumerate(PLAYER_RARITY):
            self.rarity.addItem(n, i)
        self.rarity.currentIndexChanged.connect(self.rarity_changed)
        form.addRow(tr('Nivel'), self.level)
        form.addRow(tr('Rareza'), self.rarity)
        lay.addLayout(form)

        lay.addSpacing(8)
        head = QHBoxLayout()
        head.addWidget(label(tr('ENTRENAMIENTO (JUDÍAS)'), 'CardLabel'))
        head.addStretch()
        self.train_max_btn = QPushButton(tr('Máximo'))
        self.train_max_btn.setStyleSheet('padding: 3px 10px;')
        self.train_max_btn.clicked.connect(self.train_max)
        head.addWidget(self.train_max_btn)
        lay.addLayout(head)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        self.train = []
        for slot in range(3):
            name = QLabel()
            name.setStyleSheet('background: transparent;')
            spin = QSpinBox()
            spin.valueChanged.connect(lambda v, slot=slot: self.train_changed(slot, v))
            self.train.append((name, spin))
            form.addRow(name, spin)
        lay.addLayout(form)

        lay.addSpacing(8)
        lay.addWidget(label(tr('EQUIPAMIENTO'), 'CardLabel'))
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        self.equip = {}
        for field, array, title in EQUIP_SLOTS:
            items = [it for it in cat.items.values() if it.array == array]
            cb = SearchCombo(item_model(items))
            cb.activated.connect(lambda _=0, f=field, cb=cb: self.equip_changed(f, cb))
            self.equip[field] = cb
            form.addRow(tr(title), self.with_icon(field, cb))
        lay.addLayout(form)

        lay.addSpacing(8)
        lay.addWidget(label(tr('TÉCNICAS EQUIPADAS'), 'CardLabel'))
        skills = [it for it in cat.items.values() if it.array == 'invSkill']
        m_main = item_model([it for it in skills if not it.kind.startswith(('Armadura', 'Pasiva'))])
        m_armor = item_model([it for it in skills if it.kind in ('Armadura Keshin', 'Miximax')])
        m_six = item_model([it for it in skills if re.match(r'ss\d', it.code)])
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        self.tech = {}
        for field, title in SKILL_SLOTS:
            model = m_armor if field.startswith('keshinArmed') else m_six if field == 'sixSense' else m_main
            cb = SearchCombo(model)
            cb.activated.connect(lambda _=0, f=field, cb=cb: self.tech_changed(f, cb))
            self.tech[field] = cb
            form.addRow(tr(title), self.with_icon(field, cb))
        lay.addLayout(form)
        lay.addStretch()
        self.setEnabled(False)

    def with_icon(self, field, combo):
        w = QWidget()
        w.setStyleSheet('background: transparent;')
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        icon = QLabel()
        icon.setFixedSize(30, 30)
        icon.setStyleSheet('background: transparent;')
        self.icon_labels[field] = (icon, combo)
        h.addWidget(icon)
        h.addWidget(combo, 1)
        return w

    def refresh_icons(self):
        icons = self.page.win.icons
        if icons is None:
            return
        cat = self.page.win.state.cat
        for field, (lbl, combo) in self.icon_labels.items():
            it = cat.items.get(combo.currentData() or 0)
            pm = icons.pixmap(it.icon, 30) if it else None
            lbl.setPixmap(pm) if pm else lbl.clear()
        p = self.player
        key = (cat.chara_faces.get(p.param_id) or (AVATAR_ICON if p.is_avatar else '')) if p else ''
        pm = icons.pixmap(key, 88) if key else None
        self.face.setPixmap(pm) if pm else self.face.clear()

    def load_training(self):
        p = self.player
        cap = training_cap(p.get('nowLv'))
        names = self.page.bean_names
        for (name, spin), (kind, n) in zip(self.train, training(p)):
            spin.blockSignals(True)
            spin.setRange(0, cap)
            spin.setValue(n)
            spin.setEnabled(kind is not None)
            spin.blockSignals(False)
            name.setText(names[kind] if kind is not None and kind < len(names) else tr('Hueco sin abrir'))
        self.train_max_btn.setToolTip(tr('Llenar los 3 huecos hasta {cap} judías (límite a nivel {level})', cap=cap, level=p.get('nowLv')))

    @undoable(lambda self, slot, v: tr('Entrenamiento de {name} → {value}', name=self.page.player_name(self.player), value=v))
    def train_changed(self, slot, v):
        if not self.loading and self.player:
            set_training(self.player, slot, v)
            self.page.edited()

    @undoable(lambda self: tr('Entrenar al máximo a {name}', name=self.page.player_name(self.player)))
    def train_max(self):
        if self.player:
            max_training(self.player, self.page.position(self.player))
            self.load_training()
            self.page.edited()

    def show_player(self, p):
        self.player = p
        self.setEnabled(p is not None)
        if p is None:
            self.title.setText(tr('Selecciona un jugador'))
            self.subtitle.setText('')
            self.refresh_icons()
            return
        self.loading = True
        sq = self.page.squad
        self.title.setText(self.page.player_name(p))
        sp = self.page.win.state.cat.spirits.get(p.param_id)
        self.subtitle.setText(' · '.join(tr(x) for x in (sp.element, sp.position) if x) if sp else '')
        self.level.setValue(p.get('nowLv'))
        self.rarity.setCurrentIndex(min(p.get('charaRarity'), len(PLAYER_RARITY) - 1))
        self.load_training()
        eq, te = p.equipment(), p.techniques()
        for f, cb in self.equip.items():
            cb.set_item(sq.equipped_item(eq[f]))
        for f, cb in self.tech.items():
            cb.set_item(sq.equipped_item(te[f]))
        self.loading = False
        self.refresh_icons()

    @undoable(lambda self, v: tr('Nivel de {name} → {value}', name=self.page.player_name(self.player), value=v))
    def level_changed(self, v):
        if not self.loading and self.player:
            Squad.set_level(self.player, v)
            self.load_training()
            self.page.edited()

    @undoable(lambda self, i: tr('Rareza de {name} → {value}', name=self.page.player_name(self.player), value=self.rarity.currentText()))
    def rarity_changed(self, i):
        if not self.loading and self.player:
            Squad.set_rarity(self.player, self.rarity.currentData())
            self.page.edited()

    @undoable(lambda self, field, cb: tr('{name} · {slot}: {value}', name=self.page.player_name(self.player), slot=field, value=cb.currentText()))
    def equip_changed(self, field, cb):
        if self.player:
            self.page.squad.set_equipment(self.player, field, cb.currentData())
            self.page.edited(inventory=True)
            self.refresh_icons()

    @undoable(lambda self, field, cb: tr('{name} · técnica: {value}', name=self.page.player_name(self.player), value=cb.currentText()))
    def tech_changed(self, field, cb):
        if self.player:
            self.page.squad.set_technique(self.player, field, cb.currentData())
            self.page.edited(inventory=True)
            self.refresh_icons()


class PlayersPage(TablePage):
    def __init__(self, win):
        self.win = win
        self.squad = Squad(win.state.editor)
        beans = sorted((it for it in win.state.cat.items.values() if re.match(r'tr\d', it.code)), key=lambda it: it.code)
        self.bean_names = [it.name for it in beans]
        cols = [
            Column(tr('Nombre'), self.player_name, bold=True,
                   icon=lambda p: win.state.cat.chara_faces.get(p.param_id, AVATAR_ICON if p.is_avatar else '')),
            Column(tr('Elemento'), lambda p: tr(self.spirit_attr(p, 'element')),
                   fg=lambda p: theme.ELEMENT_COLORS.get(self.spirit_attr(p, 'element'))),
            Column(tr('Pos.'), lambda p: tr(self.spirit_attr(p, 'position')), center=True),
            Column(tr('Nivel'), lambda p: p.get('nowLv'), lambda p, v: (Squad.set_level(p, int(v)), self.edited()),
                   maximum=lambda p: MAX_LEVEL, center=True, bold=True,
                   fg=lambda p: theme.ACCENT if p.get('nowLv') >= MAX_LEVEL else None),
            Column(tr('Entreno'), self.training_text, center=True,
                   fg=lambda p: theme.SUCCESS if self.fully_trained(p) else theme.TEXT_DIM),
            Column(tr('Rareza'), lambda p: PLAYER_RARITY[min(p.get('charaRarity'), len(PLAYER_RARITY) - 1)],
                   fg=lambda p: rarity_color(p.get('charaRarity'))),
        ]
        super().__init__(tr('Jugadores'), tr('Selecciona un jugador para cambiar su equipamiento y técnicas · '
                                      'Ctrl/Mayús para seleccionar varios'), cols, win.mark_dirty)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.panel = PlayerPanel(self)
        body = QHBoxLayout()
        body.setSpacing(14)
        self.lay.removeWidget(self.view)
        body.addWidget(self.view, 1)
        body.addWidget(self.panel)
        self.lay.insertLayout(2, body, 1)
        self.view.selectionModel().selectionChanged.connect(self.selection_changed)
        self.add_chips([(tr('Todos'), None), (tr('Nivel < 99'), 'low'), (tr('Nivel 99'), 'max')], self.set_filter)
        self.add_button(tr('Seleccionar visibles'), self.view.selectAll)
        self.add_button(tr('Nivel 99 a la selección'), self.max_level, primary=True)
        self.add_button(tr('Entrenar al máximo a la selección'), self.max_train,
                        tr('Llena los 3 huecos de judías hasta el límite de su nivel (2 × nivel − 18)'))
        self.add_button(tr('Fijar rareza a la selección…'), self.ask_rarity)
        self.model.set_rows(self.squad.players())
        self.view.sortByColumn(3, Qt.DescendingOrder)

    def player_name(self, p):
        if p.is_avatar:
            n = p.name_fields()
            return '⭐ ' + tr('{name} (avatar)', name=n['chrName'].data.split(b'\0')[0].decode(errors='replace'))
        return self.win.state.cat.chara_names.get(p.param_id, f'#{p.param_id:08x}')

    def spirit_attr(self, p, attr):
        sp = self.win.state.cat.spirits.get(p.param_id)
        return getattr(sp, attr) if sp else ''

    def set_filter(self, f):
        self.proxy.set_predicate(lambda p: f is None or (p.get('nowLv') >= MAX_LEVEL) == (f == 'max'))

    def selected(self):
        rows = {self.proxy.mapToSource(i).row() for i in self.view.selectionModel().selectedRows()}
        return [self.model.rows[r] for r in sorted(rows)]

    def selection_changed(self, *a):
        sel = self.selected()
        self.panel.show_player(sel[0] if len(sel) == 1 else None)
        if len(sel) > 1:
            self.panel.title.setText(tr('{n} jugadores seleccionados', n=len(sel)))
            self.panel.subtitle.setText(tr('Usa los botones de abajo para editarlos a la vez'))

    def refresh(self):
        self.model.refresh()
        if self.panel.player is not None:
            self.panel.show_player(self.panel.player)

    def edited(self, inventory=False):
        if inventory:
            self.win.state.reload_owned()
        self.win.mark_dirty()
        self.model.refresh()

    @undoable(lambda self: tr('Nivel 99 a {n} jugadores', n=len(self.selected())))
    def position(self, p):
        if p.is_avatar:
            try:
                return p.get('mainPosition')
            except KeyError:
                return None
        return self.win.state.cat.chara_positions.get(p.param_id)

    def training_text(self, p):
        slots = training(p)
        if all(k is None for k, _ in slots):
            return '—'
        return f'{sum(n for _, n in slots)}/{3 * training_cap(p.get("nowLv"))}'

    def fully_trained(self, p):
        cap = training_cap(p.get('nowLv'))
        return all(k is not None and n >= cap for k, n in training(p))

    @undoable(lambda self: tr('Entrenar al máximo a {n} jugadores', n=len(self.selected())))
    def max_train(self):
        sel = self.selected()
        for p in sel:
            max_training(p, self.position(p))
        self.edited()
        if self.panel.player is not None:
            self.panel.load_training()
        self.win.toast.show_message(tr('{n} jugadores entrenados al máximo', n=len(sel)))

    def max_level(self):
        sel = self.selected()
        for p in sel:
            Squad.set_level(p, MAX_LEVEL)
        self.edited()
        self.win.toast.show_message(tr('{n} jugadores a nivel 99', n=len(sel)))

    @undoable(lambda self: tr('Rareza de {n} jugadores', n=len(self.selected())))
    def ask_rarity(self):
        sel = self.selected()
        if not sel:
            return
        name, ok = QInputDialog.getItem(self, tr('Rareza'), tr('Rareza para {n} jugadores:', n=len(sel)), PLAYER_RARITY, 4, False)
        if ok:
            for p in sel:
                Squad.set_rarity(p, PLAYER_RARITY.index(name))
            self.edited()
            self.win.toast.show_message(tr('{n} jugadores → {value}', n=len(sel), value=name))
