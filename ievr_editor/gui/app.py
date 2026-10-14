"""Qt GUI for the IEVR save editor."""
import re
import struct
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSpinBox, QStackedWidget,
    QTableView, QVBoxLayout, QWidget,
)

from .. import catalog as catalog_mod
from .. import l5bin
from ..catalog import CHRONICLE_DIFFICULTY_NAMES
from ..editor import Editor
from ..gamedata import GameData
from ..players import EQUIP_SLOTS, MAX_LEVEL, SKILL_SLOTS, Squad
from ..savefile import USERDATA_NAME, SaveFile, find_save_dirs
from . import theme
from .tablemodel import Column, FilterProxy, RowModel, SpinDelegate

SPIRIT_TIERS = ['Verde', 'Azul', 'Morado', 'Amarillo', 'Leyenda']
DIFFICULTY_SHORT = ['Crónica', 'Desbloqueo', 'Obj. inusuales', 'Heroica', 'Heroica+', 'Legendaria']
KIND_LABEL = {'normal': 'Normal', 'hero': 'Héroe', 'basara': 'Basara'}
# charaRarity values; 0-4 follow the spirit colours, 5-7 are hero ("ídolo") cards
PLAYER_RARITY = ['Verde', 'Azul', 'Morado', 'Amarillo', 'Leyenda', 'Ídolo rojo', 'Ídolo gris', 'Ídolo rosa',
                 'Diamante']
RARITY_COLORS = theme.TIER_COLORS + ['#ff4d5e', '#b8bfcc', '#ff6fb5', '#7fe7ff']


def rarity_color(r):
    return RARITY_COLORS[r] if r < len(RARITY_COLORS) else theme.TEXT


def game_running() -> bool:
    out = subprocess.run(['ps', '-eo', 'comm'], capture_output=True, text=True).stdout
    return any(line.strip().lower() in ('nie.exe', 'eaclauncher.exe') for line in out.splitlines())


# ------------------------------------------------------------------------- state

class State:
    """Save being edited + derived lookups shared by the pages."""

    def __init__(self, save: SaveFile, cat):
        self.save = save
        self.editor = Editor(save)
        self.cat = cat
        self.dirty = False
        self.reload_owned()

    def reload_owned(self):
        self.owned = self.editor.owned_items()
        self.spirits = {k: self.editor.spirits(k) for k in ('normal', 'hero', 'basara')}

    def set_item(self, item, n):
        have = self.owned.get(item.id, 0)
        if n == have or (n == 0 and not have):
            return
        self.editor.set_item(item.array, item.id, n)
        self.owned[item.id] = n
        self.dirty = True

    def spirit_count(self, sp, tier=0):
        st = self.spirits[sp.kind].get(sp.param_id)
        return st[tier] if st and tier < len(st) else 0

    def spirit_owned(self, sp):
        return any(self.spirits[sp.kind].get(sp.param_id) or [0])

    def set_spirit(self, sp, n, tier=0):
        if self.spirit_count(sp, tier) == n or (n == 0 and sp.param_id not in self.spirits[sp.kind]):
            return
        self.editor.set_spirit(sp.kind, sp.param_id, n, tier)
        st = self.spirits[sp.kind].setdefault(sp.param_id, [0] * 6 if sp.kind == 'normal' else [0])
        st[tier] = n
        self.dirty = True

    def players(self):
        hp = l5bin.get(self.save.section(5).items, 'm_Permanent/m_saveHumanP')
        pid = l5bin.find(hp.items, 'param_id_crc').data
        return [p for p in struct.unpack(f'<{len(pid) // 4}I', pid) if p]

    def info(self):
        """Player name, play time (s) and save date shown in the sidebar."""
        out = {}
        try:
            p = self.save.get(1, 'm_Permanent')
            g = lambda n: int.from_bytes(l5bin.find(p.items, n).data, 'little')
            out['time'] = g('m_play_time')
            out['date'] = f"{g('m_save_day'):02}/{g('m_save_month'):02}/{g('m_save_year')} " \
                          f"{g('m_save_hour'):02}:{g('m_save_minute'):02}"
            e = self.save.get(0x13, 'm_Permanent/charaEditStatus[0]')
            names = l5bin.find(e, 'editName').items
            out['name'] = l5bin.find(names, 'chrName').data.split(b'\0')[0].decode()
            out['nick'] = l5bin.find(names, 'chrNickName').data.split(b'\0')[0].decode()
        except (KeyError, IndexError, UnicodeDecodeError):
            pass
        return out


# ------------------------------------------------------------------------- widgets

def label(text, name=None):
    l = QLabel(text)
    if name:
        l.setObjectName(name)
    return l


class Chips(QWidget):
    """Mutually exclusive pill buttons."""

    def __init__(self, options, on_change, default=0):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.group = QButtonGroup(self)
        for i, (text, data) in enumerate(options):
            b = QPushButton(text)
            b.setObjectName('Chip')
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(i == default)
            b.clicked.connect(lambda _=False, d=data: on_change(d))
            self.group.addButton(b)
            lay.addWidget(b)


class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName('Toast')
        self.hide()
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b'opacity', self)
        self.anim.finished.connect(self._done)
        self.timer = QTimer(self, singleShot=True, timeout=self.fade)

    def show_message(self, text, color=theme.SUCCESS):
        self.setText(text)
        self.setStyleSheet(f'border-left: 4px solid {color};')
        self.adjustSize()
        p = self.parentWidget()
        self.move(p.width() - self.width() - 28, p.height() - self.height() - 28)
        self.anim.stop()
        self.effect.setOpacity(1)
        self.show()
        self.raise_()
        self.timer.start(2600)

    def fade(self):
        self.anim.setDuration(400)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.start()

    def _done(self):
        if self.effect.opacity() == 0:
            self.hide()


class Page(QWidget):
    def __init__(self, title, subtitle):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(28, 22, 28, 22)
        self.lay.setSpacing(14)
        head = QVBoxLayout()
        head.setSpacing(2)
        head.addWidget(label(title, 'PageTitle'))
        self.sub = label(subtitle, 'PageSub')
        head.addWidget(self.sub)
        self.lay.addLayout(head)

    def refresh(self):
        pass


class TablePage(Page):
    """Search + filters + table + footer actions."""

    def __init__(self, title, subtitle, columns, on_edit):
        super().__init__(title, subtitle)
        self.model = RowModel(columns, on_edit=on_edit)
        self.proxy = FilterProxy()
        self.proxy.setSourceModel(self.model)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)  # keep source order
        self.view.setSelectionBehavior(QTableView.SelectRows)
        self.view.setShowGrid(False)
        self.view.setWordWrap(False)
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(38)
        self.view.horizontalHeader().setHighlightSections(False)
        self.view.setItemDelegate(SpinDelegate(self.model, self.proxy, self.view))
        self.view.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed |
                                  QAbstractItemView.AnyKeyPressed)
        hh = self.view.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(0, QHeaderView.Stretch)

        self.search = QLineEdit(placeholderText='🔍  Buscar por nombre…   (Ctrl+F)')
        self.search.setClearButtonEnabled(True)
        self._debounce = QTimer(self, singleShot=True, interval=120,
                                timeout=lambda: self.proxy.set_text(self.search.text()))
        self.search.textChanged.connect(lambda _: self._debounce.start())
        self.filters = QHBoxLayout()
        self.filters.setSpacing(10)
        self.filters.addWidget(self.search, 3)
        self.footer = QHBoxLayout()
        self.footer.setSpacing(8)
        self.count = label('', 'PageSub')
        self.footer.addWidget(self.count)
        self.footer.addStretch()
        for sig in (self.proxy.layoutChanged, self.proxy.rowsInserted, self.proxy.rowsRemoved,
                    self.proxy.modelReset):
            sig.connect(self.update_count)
        self.lay.addLayout(self.filters)
        self.lay.addWidget(self.view, 1)
        self.lay.addLayout(self.footer)

    def update_count(self, *a):
        self.count.setText(f'{self.proxy.rowCount()} de {self.model.rowCount()}')

    def add_button(self, text, fn, tip='', primary=False):
        b = QPushButton(text)
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        if primary:
            b.setObjectName('Primary')
        b.clicked.connect(fn)
        self.footer.addWidget(b)
        return b

    def add_combo(self, items, fn):
        cb = QComboBox()
        for text, data in items:
            cb.addItem(text, data)
        cb.currentIndexChanged.connect(lambda _: fn(cb.currentData()))
        self.filters.addWidget(cb, 1)
        return cb

    def add_chips(self, options, fn):
        c = Chips(options, fn)
        self.filters.addWidget(c)
        return c

    def after_bulk(self):
        self.model.refresh()
        self.proxy.invalidateFilter()

    def refresh(self):
        self.model.refresh()


OWNED_CHIPS = [('Todos', None), ('Tengo', True), ('No tengo', False)]


class ItemsPage(TablePage):
    """Inventory items, or skills with skills=True."""

    def __init__(self, win, skills=False):
        self.win = win
        st = lambda: win.state
        accent_if = lambda it: theme.ACCENT if st().owned.get(it.id, 0) else theme.TEXT_DIM
        cols = [
            Column('Nombre', lambda it: it.name),
            Column('Tipo', lambda it: it.kind, fg=lambda it: theme.TEXT_DIM),
            Column('Cantidad', lambda it: st().owned.get(it.id, 0), lambda it, v: st().set_item(it, int(v)),
                   maximum=lambda it: max(it.max_stack, 1), fg=accent_if, bold=True),
            Column('Máx.', lambda it: it.max_stack, fg=lambda it: theme.TEXT_DIM),
        ]
        if skills:
            cols.insert(2, Column('Obtenida', lambda it: st().owned.get(it.id, 0) > 0,
                                  lambda it, v: st().set_item(it, 1 if v else 0), check=True, center=True))
            title, sub = 'Técnicas', 'Supertécnicas, keshins, armaduras, miximax, tótems, pasivas y modos'
        else:
            title, sub = 'Objetos', 'Equipamiento, consumibles, tácticas y coleccionables · doble clic para editar'
        super().__init__(title, sub, cols, win.mark_dirty)
        self.skills = skills
        self.kind = None
        self.only_owned = None
        kinds = sorted({it.kind for it in win.state.cat.items.values() if (it.category == 'SPECIAL_SKILL') == skills})
        self.add_combo([('Todos los tipos', None)] + [(k, k) for k in kinds], self.set_kind)
        self.add_chips(OWNED_CHIPS, self.set_owned)
        if skills:
            self.add_button('Obtener todas las visibles', lambda: self.bulk(1, only_missing=True), primary=True)
        else:
            self.add_button('Añadir las que faltan (×1)', lambda: self.bulk(1, only_missing=True),
                            'Añade una unidad de cada objeto visible que no tengas')
            self.add_button('Fijar cantidad…', self.ask_bulk)
            self.add_button('Máximo a todas las visibles', lambda: self.bulk(None), primary=True)
        items = [it for it in win.state.cat.items.values() if (it.category == 'SPECIAL_SKILL') == skills]
        self.model.set_rows(sorted(items, key=lambda it: (it.kind, it.name)))
        self.apply_filter()

    def set_kind(self, k):
        self.kind = k
        self.apply_filter()

    def set_owned(self, o):
        self.only_owned = o
        self.apply_filter()

    def apply_filter(self):
        st = self.win.state

        def pred(it):
            if self.kind and it.kind != self.kind:
                return False
            return self.only_owned is None or (st.owned.get(it.id, 0) > 0) == self.only_owned
        self.proxy.set_predicate(pred)

    def bulk(self, n, only_missing=False):
        done = 0
        try:
            for it in self.proxy.visible_rows():
                if only_missing and self.win.state.owned.get(it.id, 0):
                    continue
                self.win.state.set_item(it, it.max_stack if n is None else min(n, it.max_stack))
                done += 1
        except ValueError as e:
            self.win.toast.show_message(str(e), theme.DANGER)
        self.win.mark_dirty()
        self.after_bulk()
        self.win.toast.show_message(f'{done} actualizados')

    def ask_bulk(self):
        n, ok = QInputDialog.getInt(self, 'Fijar cantidad', 'Cantidad para todos los visibles:', 99, 0, 99999)
        if ok:
            self.bulk(n)


class SpiritBulkDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Fijar cantidad de espíritus')
        f = QFormLayout(self)
        self.tier = QComboBox()
        for i, t in enumerate(SPIRIT_TIERS):
            self.tier.addItem(t, i)
        self.n = QSpinBox()
        self.n.setRange(0, 9999)
        self.n.setValue(10)
        f.addRow('Rareza (normales):', self.tier)
        f.addRow('Cantidad:', self.n)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)


class SpiritsPage(TablePage):
    def __init__(self, win):
        self.win = win
        st = lambda: win.state

        def name(s):
            return s.name + (f'  · {s.variant + 1}' if s.kind != 'normal' and win.state.cat.variants(s) > 1 else '')
        cols = [Column('Nombre', name),
                Column('Tipo', lambda s: KIND_LABEL[s.kind], fg=lambda s: theme.KIND_COLORS[KIND_LABEL[s.kind]]),
                Column('Elemento', lambda s: s.element, fg=lambda s: theme.ELEMENT_COLORS.get(s.element)),
                Column('Pos.', lambda s: s.position, center=True)]
        for t, tier in enumerate(SPIRIT_TIERS):
            color = theme.TIER_COLORS[t]
            cols.append(Column(
                tier if t else f'{tier} / Cant.',
                lambda s, t=t: '' if (t and s.kind != 'normal') else st().spirit_count(s, t),
                lambda s, v, t=t: None if (t and s.kind != 'normal') else st().set_spirit(s, int(v), t),
                maximum=lambda s: 9999, header_color=color, bold=True, center=True,
                fg=lambda s, t=t, color=color: color if st().spirit_count(s, t) else theme.SURFACE_3))
        cols.append(Column('Descripción', lambda s: s.desc, fg=lambda s: theme.TEXT_DIM))
        super().__init__('Espíritus', 'Normales por rareza, héroe y basara · doble clic en una cantidad para editarla',
                         cols, win.mark_dirty)
        hh = self.view.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(len(cols) - 1, QHeaderView.Stretch)
        self.kind = None
        self.only_owned = None
        self.add_chips([('Todos', None), ('Normales', 'normal'), ('Héroe', 'hero'), ('Basara', 'basara')],
                       self.set_kind)
        self.add_chips(OWNED_CHIPS, self.set_owned)
        self.add_button('Añadir los que faltan (×1)', lambda: self.bulk(0, 1, True))
        self.add_button('Fijar cantidad…', self.ask_bulk, primary=True)
        self.model.set_rows(sorted(win.state.cat.spirits.values(), key=lambda s: (s.kind != 'hero', s.kind, s.name)))
        self.apply_filter()

    def set_kind(self, k):
        self.kind = k
        self.apply_filter()

    def set_owned(self, o):
        self.only_owned = o
        self.apply_filter()

    def apply_filter(self):
        st = self.win.state

        def pred(s):
            if self.kind and s.kind != self.kind:
                return False
            return self.only_owned is None or st.spirit_owned(s) == self.only_owned
        self.proxy.set_predicate(pred)

    def bulk(self, tier, n, only_missing=False):
        st = self.win.state
        done = 0
        try:
            for s in self.proxy.visible_rows():
                if only_missing and st.spirit_owned(s):
                    continue
                st.set_spirit(s, n, tier if s.kind == 'normal' else 0)
                done += 1
        except ValueError as e:
            self.win.toast.show_message(str(e), theme.DANGER)
        self.win.mark_dirty()
        self.after_bulk()
        self.win.toast.show_message(f'{done} espíritus actualizados')

    def ask_bulk(self):
        d = SpiritBulkDialog(self)
        if d.exec():
            self.bulk(d.tier.currentData(), d.n.value())


class ChroniclePage(TablePage):
    def __init__(self, win):
        self.win = win
        ed = lambda: win.state.editor
        cols = [Column('Rival', lambda m: m.title, bold=True),
                Column('Ruta', lambda m: m.route + 1, center=True, fg=lambda m: theme.TEXT_DIM),
                Column('Nº', lambda m: m.order, center=True, fg=lambda m: theme.TEXT_DIM)]
        for k, short in enumerate(DIFFICULTY_SHORT, 1):
            cols.append(Column(
                short, lambda m, k=k: '✔' if ed().chronicle_cleared(m.flag_index) >= k else '·', center=True,
                fg=lambda m, k=k: theme.SUCCESS if ed().chronicle_cleared(m.flag_index) >= k else theme.SURFACE_3,
                bg=lambda m, k=k: '#173327' if ed().chronicle_cleared(m.flag_index) >= k else None, bold=True))
        super().__init__('Crónica', 'Clic en una dificultad para marcar ese partido hasta ahí · '
                                    'selecciona varios (Ctrl/Mayús o arrastrando) y aplica abajo', cols, win.mark_dirty)
        self.view.setSortingEnabled(False)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.clicked.connect(self.cell_clicked)
        self.view.selectionModel().selectionChanged.connect(self.update_selection)
        routes = sorted({m.route for m in win.state.cat.chronicle})
        self.add_chips([('Todas', None)] + [(f'Ruta {r + 1}', r) for r in routes], self.set_route)

        self.sel_label = label('', 'PageSub')
        self.footer.insertWidget(1, self.sel_label)
        self.add_button('Seleccionar visibles', self.view.selectAll)
        self.add_button('Quitar selección', self.view.clearSelection)
        self.footer.addWidget(label('   Superar hasta', 'PageSub'))
        self.target = QComboBox()
        self.target.addItem('Ninguna', 0)
        for i, n in enumerate(CHRONICLE_DIFFICULTY_NAMES, 1):
            self.target.addItem(n, i)
        self.target.setCurrentIndex(len(CHRONICLE_DIFFICULTY_NAMES))
        self.footer.addWidget(self.target)
        self.apply_btn = self.add_button('Aplicar a la selección', self.apply_selected, primary=True)
        self.model.set_rows(win.state.cat.chronicle)
        self.update_selection()

    def set_route(self, r):
        self.view.clearSelection()
        self.proxy.set_predicate(lambda m: r is None or m.route == r)

    def selected(self):
        rows = {self.proxy.mapToSource(i).row() for i in self.view.selectionModel().selectedRows()}
        return [self.model.rows[r] for r in sorted(rows)]

    def update_selection(self, *a):
        n = len(self.view.selectionModel().selectedRows())
        self.sel_label.setText(f'· {n} seleccionados' if n else '· ninguno seleccionado')
        self.apply_btn.setEnabled(n > 0)

    def set_level(self, matches, k):
        for m in matches:
            self.win.state.editor.set_chronicle(m.flag_index, k)
        self.win.mark_dirty()
        self.model.refresh()

    def cell_clicked(self, index):
        k = index.column() - 2
        if not 1 <= k <= 6 or QApplication.keyboardModifiers() & (Qt.ControlModifier | Qt.ShiftModifier):
            return
        m = self.model.rows[self.proxy.mapToSource(index).row()]
        cur = self.win.state.editor.chronicle_cleared(m.flag_index)
        self.set_level([m], k - 1 if cur == k else k)  # clicking the last cleared one undoes it

    def apply_selected(self):
        sel = self.selected()
        self.set_level(sel, self.target.currentData())
        self.win.toast.show_message(f'{len(sel)} partidos → {self.target.currentText()}')


class SearchCombo(QComboBox):
    """Combo box with type-to-filter over a shared model."""

    def __init__(self, model):
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setModel(model)
        self.setMaxVisibleItems(18)
        comp = self.completer()
        comp.setFilterMode(Qt.MatchContains)
        comp.setCompletionMode(comp.CompletionMode.PopupCompletion)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(22)

        self.currentIndexChanged.connect(lambda _: self.lineEdit().setCursorPosition(0))

    def set_item(self, item_id):
        i = self.findData(item_id or 0)
        self.setCurrentIndex(i if i >= 0 else 0)
        self.lineEdit().setCursorPosition(0)  # show the start of long names


def item_model(items):
    m = QStandardItemModel()
    empty = QStandardItem('— vacío —')
    empty.setData(0, Qt.UserRole)
    m.appendRow(empty)
    for it in sorted(items, key=lambda it: it.name):
        si = QStandardItem(f'{it.name}   · {it.kind}' if it.category == 'SPECIAL_SKILL' else it.name)
        si.setData(it.id, Qt.UserRole)
        m.appendRow(si)
    return m


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

        self.title = label('Selecciona un jugador', 'PageTitle')
        self.title.setStyleSheet('font-size: 15pt;')
        self.title.setWordWrap(True)
        self.subtitle = label('', 'CardLabel')
        lay.addWidget(self.title)
        lay.addWidget(self.subtitle)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        self.level = QSpinBox()
        self.level.setRange(1, MAX_LEVEL)
        self.level.valueChanged.connect(self.level_changed)
        self.rarity = QComboBox()
        for i, n in enumerate(PLAYER_RARITY):
            self.rarity.addItem(n, i)
        self.rarity.currentIndexChanged.connect(self.rarity_changed)
        form.addRow('Nivel', self.level)
        form.addRow('Rareza', self.rarity)
        lay.addLayout(form)

        lay.addSpacing(8)
        lay.addWidget(label('EQUIPAMIENTO', 'CardLabel'))
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        self.equip = {}
        for field, array, title in EQUIP_SLOTS:
            items = [it for it in cat.items.values() if it.array == array]
            cb = SearchCombo(item_model(items))
            cb.activated.connect(lambda _=0, f=field, cb=cb: self.equip_changed(f, cb))
            self.equip[field] = cb
            form.addRow(title, cb)
        lay.addLayout(form)

        lay.addSpacing(8)
        lay.addWidget(label('TÉCNICAS EQUIPADAS', 'CardLabel'))
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
            form.addRow(title, cb)
        lay.addLayout(form)
        lay.addStretch()
        self.setEnabled(False)

    def show_player(self, p):
        self.player = p
        self.setEnabled(p is not None)
        if p is None:
            self.title.setText('Selecciona un jugador')
            self.subtitle.setText('')
            return
        self.loading = True
        sq = self.page.squad
        self.title.setText(self.page.player_name(p))
        sp = self.page.win.state.cat.spirits.get(p.param_id)
        self.subtitle.setText(' · '.join(x for x in (sp.element, sp.position) if x) if sp else '')
        self.level.setValue(p.get('nowLv'))
        self.rarity.setCurrentIndex(min(p.get('charaRarity'), len(PLAYER_RARITY) - 1))
        eq, te = p.equipment(), p.techniques()
        for f, cb in self.equip.items():
            cb.set_item(sq.equipped_item(eq[f]))
        for f, cb in self.tech.items():
            cb.set_item(sq.equipped_item(te[f]))
        self.loading = False

    def level_changed(self, v):
        if not self.loading and self.player:
            Squad.set_level(self.player, v)
            self.page.edited()

    def rarity_changed(self, i):
        if not self.loading and self.player:
            Squad.set_rarity(self.player, self.rarity.currentData())
            self.page.edited()

    def equip_changed(self, field, cb):
        if self.player:
            self.page.squad.set_equipment(self.player, field, cb.currentData())
            self.page.edited(inventory=True)

    def tech_changed(self, field, cb):
        if self.player:
            self.page.squad.set_technique(self.player, field, cb.currentData())
            self.page.edited(inventory=True)


class PlayersPage(TablePage):
    def __init__(self, win):
        self.win = win
        self.squad = Squad(win.state.editor)
        cols = [
            Column('Nombre', self.player_name, bold=True),
            Column('Elemento', lambda p: self.spirit_attr(p, 'element'),
                   fg=lambda p: theme.ELEMENT_COLORS.get(self.spirit_attr(p, 'element'))),
            Column('Pos.', lambda p: self.spirit_attr(p, 'position'), center=True),
            Column('Nivel', lambda p: p.get('nowLv'), lambda p, v: (Squad.set_level(p, int(v)), self.edited()),
                   maximum=lambda p: MAX_LEVEL, center=True, bold=True,
                   fg=lambda p: theme.ACCENT if p.get('nowLv') >= MAX_LEVEL else None),
            Column('Rareza', lambda p: PLAYER_RARITY[min(p.get('charaRarity'), len(PLAYER_RARITY) - 1)],
                   fg=lambda p: rarity_color(p.get('charaRarity'))),
        ]
        super().__init__('Jugadores', 'Selecciona un jugador para cambiar su equipamiento y técnicas · '
                                      'Ctrl/Mayús para seleccionar varios', cols, win.mark_dirty)
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
        self.add_chips([('Todos', None), ('Nivel < 99', 'low'), ('Nivel 99', 'max')], self.set_filter)
        self.add_button('Seleccionar visibles', self.view.selectAll)
        self.add_button('Nivel 99 a la selección', self.max_level, primary=True)
        self.add_button('Fijar rareza a la selección…', self.ask_rarity)
        self.model.set_rows(self.squad.players())
        self.view.sortByColumn(3, Qt.DescendingOrder)

    def player_name(self, p):
        if p.is_avatar:
            n = p.name_fields()
            return f"⭐ {n['chrName'].data.split(b'\0')[0].decode(errors='replace')} (avatar)"
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
            self.panel.title.setText(f'{len(sel)} jugadores seleccionados')
            self.panel.subtitle.setText('Usa los botones de abajo para editarlos a la vez')

    def edited(self, inventory=False):
        if inventory:
            self.win.state.reload_owned()
        self.win.mark_dirty()
        self.model.refresh()

    def max_level(self):
        sel = self.selected()
        for p in sel:
            Squad.set_level(p, MAX_LEVEL)
        self.edited()
        self.win.toast.show_message(f'{len(sel)} jugadores a nivel 99')

    def ask_rarity(self):
        sel = self.selected()
        if not sel:
            return
        name, ok = QInputDialog.getItem(self, 'Rareza', f'Rareza para {len(sel)} jugadores:', PLAYER_RARITY, 4, False)
        if ok:
            for p in sel:
                Squad.set_rarity(p, PLAYER_RARITY.index(name))
            self.edited()
            self.win.toast.show_message(f'{len(sel)} jugadores → {name}')


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


class Card(QFrame):
    def __init__(self, title, color=theme.TEXT):
        super().__init__()
        self.setObjectName('Card')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(4)
        self.value = label('', 'CardValue')
        self.value.setStyleSheet(f'color: {color};')
        self.title = label(title, 'CardLabel')
        self.detail = label('', 'CardLabel')
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.setStyleSheet(f'QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}')
        for w in (self.title, self.value, self.bar, self.detail):
            lay.addWidget(w)

    def set(self, value, detail='', have=None, total=None):
        self.value.setText(str(value))
        self.detail.setText(detail)
        self.bar.setVisible(total is not None)
        if total:
            self.bar.setRange(0, total)
            self.bar.setValue(have)


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
        self.cards['time'].set(f'{t // 3600} h {t % 3600 // 60:02} min', f"Guardado el {info.get('date', '?')}")
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


# ------------------------------------------------------------------------- window

NAV = ['🏠  Resumen', '⚽  Jugadores', '🎒  Objetos', '🔥  Técnicas', '✨  Espíritus', '📜  Crónica', '👤  Partida']


class MainWindow(QMainWindow):
    def __init__(self, cat):
        super().__init__()
        self.cat = cat
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
        sl.addWidget(label('Save Editor para Linux', 'BrandSub'))
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

    def go(self, i):
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
        self.toast.show_message('✔  Guardado · copia del anterior en ~/.local/share/ievr-editor/backups')

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


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('IEVR Save Editor')
    app.setDesktopFileName('ievr-save-editor')
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent.parent / 'data' / 'icon.png')))
    theme.apply(app)
    try:
        gd = GameData()
    except FileNotFoundError:
        d = QFileDialog.getExistingDirectory(None, 'Selecciona la carpeta de INAZUMA ELEVEN Victory Road')
        if not d:
            return 1
        gd = GameData(d)
    splash = Splash()
    splash.show()
    app.processEvents()
    cat = catalog_mod.build(gd)
    win = MainWindow(cat)
    dirs = find_save_dirs()
    if len(sys.argv) > 1:
        win.open(sys.argv[1])
    elif dirs:
        win.open(dirs[0] / USERDATA_NAME)
    splash.close()
    win.show()
    return app.exec()
