"""Teams page: saved teams drawn on a pitch, line-up edits and the player panel."""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from ...i18n import tr
from ...teams import Team, teams
from .. import theme
from ..common import AVATAR_ICON, Page, SearchCombo, label, undoable
from .players import PlayerPanel

ROLE_COLORS = {'PR': '#ffc531', 'DF': '#3d8bff', 'MC': '#3ecf8e', 'DL': '#ff6b4a'}


class Pitch(QWidget):
    """Football pitch with one chip per formation slot."""
    clicked = Signal(int)

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.slots = []        # [(x, y, role)]
        self.chips = {}        # pos -> (name, number, face key, is captain)
        self.selected = None
        self.swap_from = None
        self.setMinimumSize(420, 460)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)

    def field_rect(self):
        r = QRectF(self.rect()).adjusted(14, 14, -14, -14)
        w = min(r.width(), r.height() * 0.72)
        return QRectF(r.center().x() - w / 2, r.top(), w, r.height())

    def slot_center(self, i):
        f = self.field_rect()
        x, y, _ = self.slots[i]
        return QPointF(f.left() + f.width() * (0.5 + x * 0.42), f.top() + f.height() * (0.06 + y * 0.86))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = self.field_rect()
        # grass with stripes
        p.setPen(Qt.NoPen)
        for k in range(10):
            p.setBrush(QColor('#1f6b3a' if k % 2 else '#237843'))
            p.drawRect(QRectF(f.left(), f.top() + f.height() * k / 10, f.width(), f.height() / 10 + 1))
        p.setPen(QPen(QColor(255, 255, 255, 150), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(f, 6, 6)
        p.drawLine(QPointF(f.left(), f.center().y()), QPointF(f.right(), f.center().y()))
        p.drawEllipse(f.center(), f.width() * 0.14, f.width() * 0.14)
        for top in (True, False):  # penalty and goal areas
            bw, bh = f.width() * 0.56, f.height() * 0.15
            gw, gh = f.width() * 0.28, f.height() * 0.06
            y0 = f.top() if top else f.bottom() - bh
            p.drawRect(QRectF(f.center().x() - bw / 2, y0, bw, bh))
            y1 = f.top() if top else f.bottom() - gh
            p.drawRect(QRectF(f.center().x() - gw / 2, y1, gw, gh))
        icons = self.page.win.icons
        for i in range(len(self.slots)):
            c = self.slot_center(i)
            role = self.slots[i][2]
            chip = self.chips.get(i)
            r = 26
            ring = theme.ACCENT if i == self.selected else ('#ff5d6c' if i == self.swap_from else ROLE_COLORS[role])
            p.setPen(QPen(QColor(ring), 4 if i in (self.selected, self.swap_from) else 3))
            p.setBrush(QColor(theme.SURFACE))
            p.drawEllipse(c, r, r)
            if chip:
                name, number, face, captain = chip
                pm = icons.pixmap(face, 2 * r - 6) if icons and face else None
                if pm:
                    path = QPainterPath()
                    path.addEllipse(c, r - 3, r - 3)
                    p.save()
                    p.setClipPath(path)
                    p.drawPixmap(int(c.x() - pm.width() / 2), int(c.y() - pm.height() / 2), pm)
                    p.restore()
                # name plate
                font = QFont(self.font())
                font.setPointSizeF(8.5)
                font.setBold(True)
                p.setFont(font)
                short = name if len(name) <= 13 else name[:12] + '…'
                text = f'{number}  {short}'
                tw = p.fontMetrics().horizontalAdvance(text) + 14
                plate = QRectF(c.x() - tw / 2, c.y() + r + 3, tw, 18)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(0, 0, 0, 170))
                p.drawRoundedRect(plate, 9, 9)
                p.setPen(QColor('#ffffff'))
                p.drawText(plate, Qt.AlignCenter, text)
                if captain:
                    b = QRectF(c.x() + r - 14, c.y() - r - 2, 18, 18)
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(theme.ACCENT))
                    p.drawEllipse(b)
                    p.setPen(QColor(theme.ACCENT_TEXT))
                    p.drawText(b, Qt.AlignCenter, 'C')
            else:
                p.setPen(QColor(theme.TEXT_DIM))
                p.drawText(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), Qt.AlignCenter, '+')
        p.end()

    def mousePressEvent(self, ev):
        for i in range(len(self.slots)):
            c = self.slot_center(i)
            if (ev.position() - c).manhattanLength() < 36:
                self.clicked.emit(i)
                return


class TeamsPage(Page):
    def __init__(self, win):
        super().__init__(tr('Equipos'), tr('Haz clic en un jugador para editarlo · «Intercambiar» y luego otro '
                                           'jugador para cambiarlos de sitio'))
        self.win = win
        self.team = None
        self.pos = None
        self.swapping = False
        self.swap_pos = None

        body = QHBoxLayout()
        body.setSpacing(14)
        # team list
        self.team_list = QListWidget()
        self.team_list.setFixedWidth(250)
        self.team_list.setStyleSheet(f'QListWidget {{ background: {theme.SURFACE}; border: 1px solid {theme.BORDER};'
                                     f' border-radius: 14px; padding: 6px; }}'
                                     f'QListWidget::item {{ padding: 8px; border-radius: 8px; }}'
                                     f'QListWidget::item:selected {{ background: {theme.SURFACE_3}; color: {theme.ACCENT}; }}')
        self.team_list.currentRowChanged.connect(self.team_selected)
        body.addWidget(self.team_list)

        # pitch + bench + actions
        mid = QVBoxLayout()
        mid.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(label(tr('Formación'), 'PageSub'))
        self.formation = QComboBox()
        self.formation.activated.connect(self.formation_changed)
        top.addWidget(self.formation, 1)
        mid.addLayout(top)
        self.pitch = Pitch(self)
        self.pitch.clicked.connect(self.slot_clicked)
        if win.icons is not None:
            win.icons.ready.connect(lambda _k: (self.pitch.update(), self.refresh_bench_icons()))
        mid.addWidget(self.pitch, 1)
        mid.addWidget(label(tr('BANQUILLO'), 'CardLabel'))
        self.bench = QListWidget()
        self.bench.setFlow(QListWidget.LeftToRight)
        self.bench.setWrapping(True)
        self.bench.setIconSize(QSize(34, 34))
        self.bench.setFixedHeight(104)
        self.bench.setStyleSheet(f'QListWidget {{ background: {theme.SURFACE}; border: 1px solid {theme.BORDER};'
                                 f' border-radius: 12px; padding: 4px; }}'
                                 f'QListWidget::item {{ padding: 4px 8px; border-radius: 8px; }}'
                                 f'QListWidget::item:selected {{ background: {theme.SURFACE_3}; color: {theme.ACCENT}; }}')
        self.bench.itemClicked.connect(lambda it: self.slot_clicked(it.data(Qt.UserRole)))
        mid.addWidget(self.bench)
        acts = QHBoxLayout()
        self.swap_btn = QPushButton(tr('⇄  Intercambiar'))
        self.swap_btn.setCheckable(True)
        self.swap_btn.toggled.connect(self.toggle_swap)
        self.captain_btn = QPushButton(tr('Ⓒ  Hacer capitán'))
        self.captain_btn.clicked.connect(self.make_captain)
        acts.addWidget(self.swap_btn)
        acts.addWidget(self.captain_btn)
        acts.addWidget(label(tr('Sustituir por'), 'PageSub'))
        self.replace = SearchCombo(self.players_model())
        self.replace.activated.connect(self.replace_player)
        acts.addWidget(self.replace, 1)
        mid.addLayout(acts)
        body.addLayout(mid, 1)

        self.panel = PlayerPanel(self)
        body.addWidget(self.panel)
        self.lay.addLayout(body, 1)
        self.load_teams()

    # PlayerPanel expects these from its page -------------------------------------
    @property
    def players_page(self):
        return self.win.players_page

    @property
    def squad(self):
        return self.players_page.squad

    @property
    def bean_names(self):
        return self.players_page.bean_names

    def player_name(self, p):
        return self.players_page.player_name(p)

    def position(self, p):
        return self.players_page.position(p)

    def edited(self, inventory=False):
        if inventory:
            self.win.state.reload_owned()
        self.win.mark_dirty()
        self.show_team()

    # data ---------------------------------------------------------------------------
    def players_by_handle(self):
        return {p.get('handle'): p for p in self.squad.players()}

    def players_model(self):
        from PySide6.QtGui import QStandardItem, QStandardItemModel
        m = QStandardItemModel()
        for p in sorted(self.squad.players(), key=lambda p: self.player_name(p)):
            it = QStandardItem(self.player_name(p))
            it.setData(p.get('handle'), Qt.UserRole)
            m.appendRow(it)
        return m

    def team_label(self, t: Team, all_teams):
        name = t.name
        if not name:
            main = next((x.name for x in all_teams if x.set_index == t.set_index and x.name), '')
            name = (main or tr('Equipo {n}', n=t.set_index + 1)) + ' · ' + tr('variante {n}', n=t.team_index + 1)
        f = self.win.state.cat.formations.get(t.formation_id)
        return f'{name}\n{f.name if f else tr("sin formación")}  ·  {tr("{n} jugadores", n=t.row["memberNum"])}'

    def load_teams(self):
        self.teams = teams(self.win.state.editor)
        self.team_list.blockSignals(True)
        self.team_list.clear()
        for t in self.teams:
            self.team_list.addItem(self.team_label(t, self.teams))
            self.team_list.item(self.team_list.count() - 1).setToolTip(self.team_label(t, self.teams))
        self.team_list.blockSignals(False)
        if self.teams:
            self.team_list.setCurrentRow(0)
            self.team_selected(0)

    def team_selected(self, row):
        if 0 <= row < len(self.teams):
            self.team = self.teams[row]
            self.pos = None
            self.show_team()

    def formation_of(self, t):
        cat = self.win.state.cat
        f = cat.formations.get(t.formation_id)
        if f is None:  # variants without their own formation use the main team's
            main = next((x for x in self.teams if x.set_index == t.set_index and x.formation_id in cat.formations), None)
            f = cat.formations.get(main.formation_id) if main else next(iter(cat.formations.values()))
        return f

    def show_team(self):
        t = self.team
        if t is None:
            return
        f = self.formation_of(t)
        cat = self.win.state.cat
        by_handle = self.players_by_handle()
        self.pitch.slots = f.slots
        self.pitch.chips = {}
        starters = len(f.slots)
        bench = []
        for m in t.members():
            h = m['charaStHdl']
            if not h:
                continue
            p = by_handle.get(h)
            name = self.player_name(p) if p else '?'
            face = (cat.chara_faces.get(p.param_id) or (AVATAR_ICON if p.is_avatar else '')) if p else ''
            if m['scPosNo'] < starters:
                self.pitch.chips[m['scPosNo']] = (name.replace('⭐ ', ''), m['uniformNo'], face, h == t.captain)
            else:
                bench.append((m['scPosNo'], m['uniformNo'], name, face))
        self.pitch.selected = self.pos if self.pos is not None and self.pos < starters else None
        self.pitch.swap_from = self.swap_pos if self.swapping else None
        self.pitch.update()
        self.bench.clear()
        for pos, number, name, face in sorted(bench):
            it = QListWidgetItem(f'{number}  {name}')
            it.setData(Qt.UserRole, pos)
            it.setData(Qt.UserRole + 1, face)
            self.bench.addItem(it)
            if pos == self.pos:
                it.setSelected(True)
        free = [p for p in range(starters, starters + 9) if p not in {b[0] for b in bench}]
        if free and t.row['memberNum'] < 20:
            it = QListWidgetItem(tr('＋ hueco libre'))
            it.setData(Qt.UserRole, free[0])
            self.bench.addItem(it)
        self.refresh_bench_icons()
        # formation choices with the same number of players
        self.formation.blockSignals(True)
        self.formation.clear()
        for fid, ff in sorted(cat.formations.items(), key=lambda kv: kv[1].name):
            if len(ff.slots) == starters:
                self.formation.addItem(ff.name, fid)
        self.formation.setCurrentIndex(max(0, self.formation.findData(f.id)))
        self.formation.blockSignals(False)
        member = t.at(self.pos) if self.pos is not None else None
        p = by_handle.get(member['charaStHdl']) if member else None
        self.panel.show_player(p)
        self.captain_btn.setEnabled(p is not None and member['charaStHdl'] != t.captain)

    def refresh_bench_icons(self):
        icons = self.win.icons
        if icons is None:
            return
        from PySide6.QtGui import QIcon
        for i in range(self.bench.count()):
            it = self.bench.item(i)
            pm = icons.pixmap(it.data(Qt.UserRole + 1), 34) if it.data(Qt.UserRole + 1) else None
            if pm:
                it.setIcon(QIcon(pm))

    def refresh(self):
        self.replace.setModel(self.players_model())
        self.load_teams_keep()

    def load_teams_keep(self):
        row = self.team_list.currentRow()
        self.teams = teams(self.win.state.editor)
        for i, t in enumerate(self.teams):
            if i < self.team_list.count():
                self.team_list.item(i).setText(self.team_label(t, self.teams))
        if 0 <= row < len(self.teams):
            self.team = self.teams[row]
        self.show_team()

    # interactions -----------------------------------------------------------------
    def toggle_swap(self, on):
        self.swapping = on and self.pos is not None
        self.swap_pos = self.pos
        if on and self.pos is None:
            self.swap_btn.setChecked(False)
        self.show_team()

    def slot_clicked(self, pos):
        if self.swapping and pos != self.swap_pos:
            self.do_swap(self.swap_pos, pos)
            self.swap_btn.setChecked(False)
            self.pos = pos
            self.show_team()
            return
        self.pos = pos
        self.show_team()

    @undoable(lambda self, a, b: tr('{team}: intercambiar posiciones', team=self.team.name or tr('Equipo')))
    def do_swap(self, a, b):
        self.team.swap(a, b)
        self.win.mark_dirty()

    @undoable(lambda self, *_: tr('{team}: sustituir jugador', team=self.team.name or tr('Equipo')))
    def replace_player(self, *_):
        h = self.replace.currentData()
        if self.team is None or self.pos is None or not h:
            return
        try:
            self.team.put(self.pos, h)
        except ValueError:
            self.win.toast.show_message(tr('El equipo está completo'), theme.DANGER)
            return
        self.win.mark_dirty()
        self.load_teams_keep()

    @undoable(lambda self: tr('{team}: nuevo capitán', team=self.team.name or tr('Equipo')))
    def make_captain(self):
        m = self.team.at(self.pos) if self.team and self.pos is not None else None
        if m:
            self.team.set_captain(m['charaStHdl'])
            self.win.mark_dirty()
            self.show_team()

    @undoable(lambda self, _i: tr('{team}: formación → {value}', team=self.team.name or tr('Equipo'),
                                  value=self.formation.currentText()))
    def formation_changed(self, _i):
        if self.team is not None:
            self.team.set_formation(self.formation.currentData())
            self.win.mark_dirty()
            self.load_teams_keep()
