"""Shared state, constants and base widgets of the GUI."""
import functools
import struct
import subprocess
import sys

from PySide6.QtCore import QPropertyAnimation, QSize, Qt, QTimer
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QProgressBar, QPushButton, QTableView, QVBoxLayout, QWidget,
)

from .. import l5bin
from ..editor import Editor
from ..journal import Journal
from ..savefile import SaveFile
from . import theme
from .tablemodel import FilterProxy, RowModel, SpinDelegate
from ..i18n import tr


SPIRIT_TIERS = [tr('Verde'), tr('Azul'), tr('Morado'), tr('Amarillo'), tr('Leyenda')]
DIFFICULTY_SHORT = [tr('Crónica'), tr('Desbloqueo'), tr('Obj. inusuales'), tr('Heroica'), tr('Heroica+'), tr('Legendaria')]
KIND_LABEL = {'normal': tr('Normal'), 'hero': tr('Héroe'), 'basara': tr('Basara')}
KIND_COLORS = {'normal': theme.KIND_COLORS['Normal'], 'hero': theme.KIND_COLORS['Héroe'],
               'basara': theme.KIND_COLORS['Basara']}
AVATAR_ICON = 'file:icon_ava_face00'  # generic avatar face from the avatar creator
# charaRarity values; 0-4 follow the spirit colours, 5-7 are hero ("ídolo") cards
PLAYER_RARITY = [tr('Verde'), tr('Azul'), tr('Morado'), tr('Amarillo'), tr('Leyenda'), tr('Ídolo rojo'), tr('Ídolo gris'), tr('Ídolo rosa'),
                 tr('Diamante')]
RARITY_COLORS = theme.TIER_COLORS + ['#ff4d5e', '#b8bfcc', '#ff6fb5', '#7fe7ff']


def rarity_color(r):
    return RARITY_COLORS[r] if r < len(RARITY_COLORS) else theme.TEXT


def game_running() -> bool:
    """Whether the game (or its EAC launcher) is running; under Proton it shows up as nie.exe too."""
    try:
        if sys.platform == 'win32':
            out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
            names = [line.split(',')[0].strip('"') for line in out.splitlines()]
        else:
            names = subprocess.run(['ps', '-eo', 'comm'], capture_output=True, text=True).stdout.splitlines()
    except OSError:
        return False
    return any(n.strip().lower() in ('nie.exe', 'eaclauncher.exe') for n in names)


# ------------------------------------------------------------------------- state

class State:
    """Save being edited + derived lookups shared by the pages."""

    def __init__(self, save: SaveFile, cat):
        self.save = save
        self.editor = Editor(save)
        self.cat = cat
        self.journal = Journal()
        self.journal.activate()
        self.reload_owned()

    @property
    def dirty(self):
        return self.journal.dirty

    def reload_owned(self):
        self.owned = self.editor.owned_items()
        self.spirits = {k: self.editor.spirits(k) for k in ('normal', 'hero', 'basara')}

    def set_item(self, item, n):
        have = self.owned.get(item.id, 0)
        if n == have or (n == 0 and not have):
            return
        self.editor.set_item(item.array, item.id, n)
        self.owned[item.id] = n

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


def undoable(label):
    """Run a page method as one undo step; ``label`` is a string or ``f(self, *args)``."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            win = self.win if hasattr(self, 'win') else self.page.win
            try:
                text = label(self, *args, **kwargs) if callable(label) else label
            except Exception:  # a label must never block the edit
                text = fn.__name__
            with win.action(text):
                return fn(self, *args, **kwargs)
        return wrapper
    return deco


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
        if getattr(self, 'win', None) is not None:
            self.model.action = self.win.action
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
        self.view.verticalHeader().setDefaultSectionSize(44)
        self.view.setIconSize(QSize(34, 34))
        win = getattr(self, 'win', None)
        if win is not None and win.icons is not None:
            self.model.icons = win.icons
            win.icons.ready.connect(lambda _key: self.view.viewport().update())
        self.view.horizontalHeader().setHighlightSections(False)
        self.view.setItemDelegate(SpinDelegate(self.model, self.proxy, self.view))
        self.view.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed |
                                  QAbstractItemView.AnyKeyPressed)
        hh = self.view.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(0, QHeaderView.Stretch)

        self.search = QLineEdit(placeholderText=tr('🔍  Buscar por nombre…   (Ctrl+F)'))
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
        self.count.setText(tr('{shown} de {total}', shown=self.proxy.rowCount(), total=self.model.rowCount()))

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


OWNED_CHIPS = [(tr('Todos'), None), (tr('Tengo'), True), (tr('No tengo'), False)]


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
    empty = QStandardItem(tr('— vacío —'))
    empty.setData(0, Qt.UserRole)
    m.appendRow(empty)
    for it in sorted(items, key=lambda it: it.name):
        si = QStandardItem(it.name)
        si.setData(it.id, Qt.UserRole)
        si.setToolTip(tr(it.kind))
        m.appendRow(si)
    return m


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
