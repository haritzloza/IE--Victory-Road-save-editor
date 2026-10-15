"""Items page."""

from PySide6.QtWidgets import (
    QInputDialog,
)

from .. import theme
from ..iconloader import BADGE_COLORS
from ..tablemodel import Column
from ..common import (TablePage, OWNED_CHIPS, undoable)
from ...i18n import tr


class ItemsPage(TablePage):
    """Inventory items, or skills with skills=True."""

    def __init__(self, win, skills=False):
        self.win = win
        st = lambda: win.state
        accent_if = lambda it: theme.ACCENT if st().owned.get(it.id, 0) else theme.TEXT_DIM
        cols = [
            Column(tr('Nombre'), lambda it: it.name, icon=lambda it: it.icon),
            Column(tr('Tipo'), lambda it: tr(it.kind), fg=lambda it: theme.TEXT_DIM),
            Column(tr('Cantidad'), lambda it: st().owned.get(it.id, 0), lambda it, v: st().set_item(it, int(v)),
                   maximum=lambda it: max(it.max_stack, 1), fg=accent_if, bold=True),
            Column(tr('Máx.'), lambda it: it.max_stack, fg=lambda it: theme.TEXT_DIM),
        ]
        if skills:
            cols.insert(2, Column(tr('Obtenida'), lambda it: st().owned.get(it.id, 0) > 0,
                                  lambda it, v: st().set_item(it, 1 if v else 0), check=True, center=True))
            cols[2:2] = [
                Column(tr('Elemento'), lambda it: tr(it.element) if it.element else '', fg=lambda it: BADGE_COLORS.get(it.element)),
                Column(tr('Potencia'), lambda it: it.power or '', center=True, bold=True),
                Column('TP', lambda it: it.tp or '', center=True, fg=lambda it: theme.TEXT_DIM),
            ]
            title, sub = tr('Técnicas'), tr('Supertécnicas, keshins, armaduras, miximax, tótems, pasivas y modos')
        else:
            title, sub = tr('Objetos'), tr('Equipamiento, consumibles, tácticas y coleccionables · doble clic para editar')
        super().__init__(title, sub, cols, win.mark_dirty)
        self.skills = skills
        self.kind = None
        self.only_owned = None
        kinds = sorted({it.kind for it in win.state.cat.items.values() if (it.category == 'SPECIAL_SKILL') == skills})
        self.add_combo([(tr('Todos los tipos'), None)] + [(tr(k), k) for k in kinds], self.set_kind)
        self.element = None
        if skills:
            self.add_chips([(tr('Todos'), None)] + [(tr(e), e) for e in ('Viento', 'Bosque', 'Fuego', 'Montaña', 'Neutro')],
                           self.set_element)
        self.add_chips(OWNED_CHIPS, self.set_owned)
        if skills:
            self.add_button(tr('Obtener todas las visibles'), lambda: self.bulk(1, only_missing=True), primary=True)
        else:
            self.add_button(tr('Añadir las que faltan (×1)'), lambda: self.bulk(1, only_missing=True),
                            tr('Añade una unidad de cada objeto visible que no tengas'))
            self.add_button(tr('Fijar cantidad…'), self.ask_bulk)
            self.add_button(tr('Máximo a todas las visibles'), lambda: self.bulk(None), primary=True)
        items = [it for it in win.state.cat.items.values() if (it.category == 'SPECIAL_SKILL') == skills]
        self.model.set_rows(sorted(items, key=lambda it: (it.kind, it.name)))
        self.apply_filter()

    def set_kind(self, k):
        self.kind = k
        self.apply_filter()

    def set_element(self, e):
        self.element = e
        self.apply_filter()

    def set_owned(self, o):
        self.only_owned = o
        self.apply_filter()

    def apply_filter(self):
        st = self.win.state

        def pred(it):
            if self.kind and it.kind != self.kind:
                return False
            if self.element and it.element != self.element:
                return False
            return self.only_owned is None or (st.owned.get(it.id, 0) > 0) == self.only_owned
        self.proxy.set_predicate(pred)

    @undoable(lambda self, n, only_missing=False: (tr('Añadir los que faltan') if only_missing else tr('Máximo') if n is None else tr('Fijar cantidad {n}', n=n)) + ' · ' + (tr(self.kind) if self.kind else tr('técnicas' if self.skills else 'objetos')))
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
        self.win.toast.show_message(tr('{n} actualizados', n=done))

    def ask_bulk(self):
        n, ok = QInputDialog.getInt(self, tr('Fijar cantidad'), tr('Cantidad para todos los visibles:'), 99, 0, 99999)
        if ok:
            self.bulk(n)
