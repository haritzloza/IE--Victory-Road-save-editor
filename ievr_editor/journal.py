"""Undo/redo journal for save edits.

Every function that mutates save data calls ``touch(buffer)`` first; inside an
``action(label)`` the journal keeps the buffer's previous bytes, so the whole
action can be undone or redone as one step. Outside an action ``touch`` does
nothing (scripted edits are not journaled).
"""
from contextlib import contextmanager
from typing import List, Optional

_active: Optional['Journal'] = None


def touch(buf: bytearray):
    if _active is not None:
        _active._touch(buf)


class Step:
    def __init__(self, label: str):
        self.label = label
        self.before = {}   # id(buf) -> (buf, bytes)
        self.after = {}

    def changed(self):
        return any(bytes(buf) != old for buf, old in self.before.values())


class Journal:
    def __init__(self):
        self.undo: List[Step] = []
        self.redo: List[Step] = []
        self._current: Optional[Step] = None
        self._saved_top = None  # undo[-1] at the last save (None = nothing)

    def activate(self):
        global _active
        _active = self

    def _touch(self, buf):
        if self._current is not None and id(buf) not in self._current.before:
            self._current.before[id(buf)] = (buf, bytes(buf))

    @contextmanager
    def action(self, label: str):
        if self._current is not None:  # nested: belongs to the outer action
            yield
            return
        self._current = Step(label)
        try:
            yield
        finally:
            step, self._current = self._current, None
            if step.changed():
                self.undo.append(step)
                self.redo.clear()

    def undo_last(self) -> Optional[str]:
        if not self.undo:
            return None
        step = self.undo.pop()
        step.after = {k: (buf, bytes(buf)) for k, (buf, _) in step.before.items()}
        for buf, old in step.before.values():
            buf[:] = old
        self.redo.append(step)
        return step.label

    def redo_last(self) -> Optional[str]:
        if not self.redo:
            return None
        step = self.redo.pop()
        for buf, new in step.after.values():
            buf[:] = new
        self.undo.append(step)
        return step.label

    def mark_saved(self):
        self._saved_top = self.undo[-1] if self.undo else None

    @property
    def dirty(self) -> bool:
        return (self.undo[-1] if self.undo else None) is not self._saved_top

    def pending(self) -> List[str]:
        """Labels of the actions done since the last save (oldest first)."""
        if self._saved_top is None:
            return [s.label for s in self.undo]
        if self._saved_top in self.undo:
            return [s.label for s in self.undo[self.undo.index(self._saved_top) + 1:]]
        return [s.label for s in self.undo] + ['(se han deshecho cambios ya guardados)']
