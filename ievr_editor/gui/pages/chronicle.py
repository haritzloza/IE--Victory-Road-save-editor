"""Chronicle page."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox,
)

from ...catalog import CHRONICLE_DIFFICULTY_NAMES
from .. import theme
from ..tablemodel import Column
from ..common import (DIFFICULTY_SHORT, label, TablePage, undoable)


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

    @undoable(lambda self, matches, k: f'Crónica: {len(matches)} partido(s) → {(["ninguna"] + CHRONICLE_DIFFICULTY_NAMES)[k]}')
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
