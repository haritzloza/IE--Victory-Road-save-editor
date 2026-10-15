"""Spirits page."""

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHeaderView, QSpinBox,
)

from .. import theme
from ..tablemodel import Column
from ..common import (SPIRIT_TIERS, KIND_LABEL, TablePage, OWNED_CHIPS)


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
        cols = [Column('Nombre', name, icon=lambda s: s.face),
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
        super().__init__('Espíritus', 'Normales por rareza, héroe y basara · doble clic en una cantidad para editarla · '
                                      'pasa el ratón por encima para ver la descripción',
                         cols, win.mark_dirty)
        hh = self.view.horizontalHeader()
        # fixed width: resizing to contents would ask every row for its icon
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
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
