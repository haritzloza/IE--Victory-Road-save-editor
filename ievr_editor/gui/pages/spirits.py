"""Spirits page."""

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHeaderView, QSpinBox,
)

from .. import theme
from ..tablemodel import Column
from ..common import (SPIRIT_TIERS, KIND_LABEL, TablePage, OWNED_CHIPS, undoable, KIND_COLORS)
from ...i18n import tr


class SpiritBulkDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr('Fijar cantidad de espíritus'))
        f = QFormLayout(self)
        self.tier = QComboBox()
        for i, t in enumerate(SPIRIT_TIERS):
            self.tier.addItem(t, i)
        self.n = QSpinBox()
        self.n.setRange(0, 9999)
        self.n.setValue(10)
        f.addRow(tr('Rareza (normales):'), self.tier)
        f.addRow(tr('Cantidad:'), self.n)
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
        cols = [Column(tr('Nombre'), name, icon=lambda s: s.face),
                Column(tr('Tipo'), lambda s: KIND_LABEL[s.kind], fg=lambda s: KIND_COLORS[s.kind]),
                Column(tr('Elemento'), lambda s: tr(s.element) if s.element else '', fg=lambda s: theme.ELEMENT_COLORS.get(s.element)),
                Column(tr('Pos.'), lambda s: tr(s.position) if s.position else '', center=True)]
        for t, tier in enumerate(SPIRIT_TIERS):
            color = theme.TIER_COLORS[t]
            cols.append(Column(
                tier if t else tr('{tier} / Cant.', tier=tier),
                lambda s, t=t: '' if (t and s.kind != 'normal') else st().spirit_count(s, t),
                lambda s, v, t=t: None if (t and s.kind != 'normal') else st().set_spirit(s, int(v), t),
                maximum=lambda s: 9999, header_color=color, bold=True, center=True,
                fg=lambda s, t=t, color=color: color if st().spirit_count(s, t) else theme.SURFACE_3))
        super().__init__(tr('Espíritus'), tr('Normales por rareza, héroe y basara · doble clic en una cantidad para editarla · '
                                      'pasa el ratón por encima para ver la descripción'),
                         cols, win.mark_dirty)
        hh = self.view.horizontalHeader()
        # fixed width: resizing to contents would ask every row for its icon
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        self.kind = None
        self.only_owned = None
        self.add_chips([(tr('Todos'), None), (tr('Normales'), 'normal'), ('Héroe', 'hero'), ('Basara', 'basara')],
                       self.set_kind)
        self.add_chips(OWNED_CHIPS, self.set_owned)
        self.add_button('Añadir los que faltan (×1)', lambda: self.bulk(0, 1, True))
        self.add_button(tr('Fijar cantidad…'), self.ask_bulk, primary=True)
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

    @undoable(lambda self, tier, n, only_missing=False: (tr('Añadir espíritus que faltan') if only_missing else tr('Espíritus: fijar {n} ({tier})', n=n, tier=SPIRIT_TIERS[tier])))
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
        self.win.toast.show_message(tr('{n} espíritus actualizados', n=done))

    def ask_bulk(self):
        d = SpiritBulkDialog(self)
        if d.exec():
            self.bulk(d.tier.currentData(), d.n.value())
