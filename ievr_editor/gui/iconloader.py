"""Background icon loading for the tables (one worker thread, memory + disk cache)."""
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QPixmap

from ..icons import IconStore


class _Job(QRunnable):
    def __init__(self, loader, key):
        super().__init__()
        self.loader, self.key = loader, key

    def run(self):
        path = self.loader.store.png(self.key)
        self.loader._done.emit(self.key, str(path) if path else '')


class IconLoader(QObject):
    """``pixmap(key)`` returns the icon if ready, else schedules it and returns None."""
    ready = Signal(str)
    _done = Signal(str, str)

    def __init__(self, store: IconStore, size=34):
        super().__init__()
        self.store = store
        self.size = size
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)  # game file readers are not thread safe
        self.cache = {}
        self.pending = set()
        self._seq = 0  # newer requests run first: what is on screen now beats old scroll positions
        self._done.connect(self._finish)

    def pixmap(self, key, size=None):
        if not key:
            return None
        size = size or self.size
        pm = self.cache.get((key, size))
        if pm is not None:
            return None if pm.isNull() else pm
        base = self.cache.get((key, None))
        if base is not None:
            pm = QPixmap() if base.isNull() else base.scaled(size, size, Qt.KeepAspectRatio,
                                                             Qt.SmoothTransformation)
            self.cache[(key, size)] = pm
            return None if pm.isNull() else pm
        if key not in self.pending:
            self.pending.add(key)
            self._seq += 1
            self.pool.start(_Job(self, key), self._seq)
        return None

    def _finish(self, key, path):
        self.pending.discard(key)
        self.cache[(key, None)] = QPixmap(path) if path else QPixmap()
        self.ready.emit(key)
