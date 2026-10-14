"""Generic editable table model + filter used by every tab."""
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QSpinBox, QStyledItemDelegate


@dataclass
class Column:
    title: str
    get: Callable[[Any], Any]
    set: Optional[Callable[[Any, Any], None]] = None   # editable when present
    check: bool = False                                  # render as checkbox
    maximum: Callable[[Any], int] = lambda row: 99999
    width: int = 0
    fg: Optional[Callable[[Any], Optional[str]]] = None   # text colour
    bg: Optional[Callable[[Any], Optional[str]]] = None   # background colour
    bold: bool = False
    center: bool = False
    header_color: Optional[str] = None


class RowModel(QAbstractTableModel):
    def __init__(self, columns: List[Column], rows=None, on_edit=None):
        super().__init__()
        self.columns = columns
        self.rows = rows or []
        self.on_edit = on_edit

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def refresh(self):
        if self.rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows) - 1, len(self.columns) - 1))

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation != Qt.Horizontal:
            return None
        c = self.columns[section]
        if role == Qt.DisplayRole:
            return c.title
        if role == Qt.ForegroundRole and c.header_color:
            return QBrush(QColor(c.header_color))
        return None

    def flags(self, index):
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        c = self.columns[index.column()]
        if c.set:
            f |= Qt.ItemIsUserCheckable if c.check else Qt.ItemIsEditable
        return f

    def data(self, index, role=Qt.DisplayRole):
        row, c = self.rows[index.row()], self.columns[index.column()]
        v = c.get(row)
        if c.check:
            if role == Qt.CheckStateRole:
                return Qt.Checked if v else Qt.Unchecked
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            return v
        if role == Qt.UserRole:  # sort key
            return v
        if role == Qt.ToolTipRole and getattr(row, 'desc', ''):
            return row.desc
        if role == Qt.TextAlignmentRole:
            if c.center:
                return int(Qt.AlignCenter)
            if isinstance(v, int) and not isinstance(v, bool):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return None
        if role == Qt.ForegroundRole and c.fg:
            col = c.fg(row)
            return QBrush(QColor(col)) if col else None
        if role == Qt.BackgroundRole and c.bg:
            col = c.bg(row)
            return QBrush(QColor(col)) if col else None
        if role == Qt.FontRole and c.bold:
            f = QFont()
            f.setBold(True)
            return f
        return None

    def setData(self, index, value, role=Qt.EditRole):
        row, c = self.rows[index.row()], self.columns[index.column()]
        if not c.set:
            return False
        if c.check and role == Qt.CheckStateRole:
            value = Qt.CheckState(value) == Qt.Checked
        elif role != Qt.EditRole:
            return False
        c.set(row, value)
        self.dataChanged.emit(self.index(index.row(), 0), self.index(index.row(), len(self.columns) - 1))
        if self.on_edit:
            self.on_edit()
        return True


class SpinDelegate(QStyledItemDelegate):
    """Integer editor bounded by the column's maximum for that row."""

    def __init__(self, model: RowModel, proxy: QSortFilterProxyModel, parent=None):
        super().__init__(parent)
        self.model, self.proxy = model, proxy

    def createEditor(self, parent, option, index):
        src = self.proxy.mapToSource(index)
        col = self.model.columns[src.column()]
        sb = QSpinBox(parent)
        sb.setRange(0, col.maximum(self.model.rows[src.row()]))
        return sb


class FilterProxy(QSortFilterProxyModel):
    """Text search over the first column plus an arbitrary row predicate."""

    def __init__(self):
        super().__init__()
        self.text = ''
        self.predicate = lambda row: True
        self.setSortRole(Qt.UserRole)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.setSortLocaleAware(True)

    def set_text(self, t):
        self.text = t.casefold()
        self.invalidateFilter()

    def set_predicate(self, p):
        self.predicate = p
        self.invalidateFilter()

    def filterAcceptsRow(self, r, parent):
        m = self.sourceModel()
        row = m.rows[r]
        if self.text and self.text not in str(m.columns[0].get(row)).casefold():
            return False
        return self.predicate(row)

    def visible_rows(self):
        m = self.sourceModel()
        return [m.rows[self.mapToSource(self.index(i, 0)).row()] for i in range(self.rowCount())]
