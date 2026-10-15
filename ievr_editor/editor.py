"""High-level edits on a SaveFile (inventory, spirits, chronicle progress)."""
import struct
from dataclasses import dataclass
from typing import Dict, List

from . import journal, l5bin
from .savefile import SaveFile

INVENTORY_SECTION = 0x04
SPIRIT_SECTION = 0x12
FLAG_SECTION = 0x02

# (handle category byte, handle group) per inventory array; matches the
# handles the game itself assigns (see slot_handle).
INVENTORY_HANDLE = {
    'invConsume': (0x00, 0), 'invShoes': (0x20, 0), 'invMisanga': (0x40, 0),
    'invAccessory': (0x60, 0), 'invSpecial': (0x80, 0), 'invFashion': (0xA0, 0),
    'invTeamItem': (0xC0, 0), 'invCostume': (0xE0, 0),
    'invCraftObj': (0x00, 1), 'invAnimal': (0x20, 1), 'invTitle': (0x40, 1),
    'invSkill': (0x60, 1), 'invKizunaLink': (0x80, 1), 'invNamePlate': (0xA0, 1),
    'invPerformance': (0xC0, 1), 'invEquipToken': (0xE0, 1),
}
SPIRIT_HANDLE = {'normalSpiritInfo': 0x00, 'heroSpiritInfo': 0x20, 'basaraSpiritInfo': 0x80,
                 'seasonalNormalSpiritInfo': 0xA0}
SPIRIT_ARRAY = {'normal': 'normalSpiritInfo', 'hero': 'heroSpiritInfo', 'basara': 'basaraSpiritInfo'}

ATTR_OWNED = 3
FLAG_OWNED = 2


def slot_handle(index: int, category: int, group: int) -> int:
    """Handle the game stores for slot ``index`` of an inventory-like array."""
    low = (index & 0xFF) | ((category | (index >> 8)) << 8)
    high = ((index + 1) << 2) | group
    return low | high << 16


def _int(v: l5bin.Value) -> int:
    return int.from_bytes(v.data, 'little')


def _set(v: l5bin.Value, n: int):
    journal.touch(v.data)
    v.data[:] = n.to_bytes(len(v.data), 'little')


class Row:
    """Field access to one array element."""

    def __init__(self, items):
        self.f = {it.name: it for it in items if isinstance(it, l5bin.Value)}

    def __getitem__(self, k):
        return _int(self.f[k])

    def __setitem__(self, k, n):
        _set(self.f[k], n)

    def __contains__(self, k):
        return k in self.f


@dataclass
class InvEntry:
    array: str
    index: int
    item_id: int
    count: int
    equipped: int


class Editor:
    def __init__(self, save: SaveFile):
        self.save = save

    # ---------------------------------------------------------------- inventory
    def _inv_root(self):
        return self.save.section(INVENTORY_SECTION).items

    def _inv_array(self, name) -> l5bin.Array:
        return l5bin.find(self._inv_root(), name)

    def _next_get_order(self) -> int:
        v = l5bin.find(self._inv_root(), 'm_get_order_count')
        n = _int(v) + 1
        _set(v, n)
        return n

    def inventory(self, array: str) -> List[InvEntry]:
        out = []
        for i, el in enumerate(self._inv_array(array).elements):
            r = Row(el)
            if r['item_id']:
                out.append(InvEntry(array, i, r['item_id'], r['stockNum'] if 'stockNum' in r else 1,
                                    r['equipment_num'] if 'equipment_num' in r else 0))
        return out

    def owned_items(self) -> Dict[int, int]:
        """item_id -> total count over all inventory arrays."""
        out = {}
        for name in INVENTORY_HANDLE:
            try:
                entries = self.inventory(name)
            except KeyError:  # array not present in this save version
                continue
            for e in entries:
                out[e.item_id] = out.get(e.item_id, 0) + e.count
        return out

    def set_item(self, array: str, item_id: int, count: int) -> InvEntry:
        """Set the stock of an item, adding it to a free slot if it isn't owned."""
        arr = self._inv_array(array)
        rows = [Row(el) for el in arr.elements]
        for i, r in enumerate(rows):
            if r['item_id'] == item_id:
                if 'stockNum' in r:
                    r['stockNum'] = max(count, r['equipment_num'] if 'equipment_num' in r else 0)
                if r['attr'] != ATTR_OWNED:  # an entry kept after selling/using everything
                    r['attr'], r['flag'] = ATTR_OWNED, FLAG_OWNED
                return InvEntry(array, i, item_id, count, r['equipment_num'] if 'equipment_num' in r else 0)
        free = next((i for i, r in enumerate(rows) if r['item_id'] == 0), None)
        if free is None:
            raise ValueError(f'{array}: no free slots')
        r = rows[free]
        cat, group = INVENTORY_HANDLE[array]
        r['handle'] = slot_handle(free, cat, group)
        r['item_id'] = item_id
        r['get_order'] = self._next_get_order()
        r['attr'], r['flag'] = ATTR_OWNED, FLAG_OWNED
        if 'stockNum' in r:
            r['stockNum'] = count
        return InvEntry(array, free, item_id, count, 0)

    # ---------------------------------------------------------------- spirits
    def _spirit_root(self):
        return l5bin.find(self.save.section(SPIRIT_SECTION).items, 'm_Permanent').items

    def spirits(self, kind: str) -> Dict[int, List[int]]:
        """param_id -> stock per tier (normal: 6 u16 tiers, hero/basara: 1)."""
        out = {}
        for el in l5bin.find(self._spirit_root(), SPIRIT_ARRAY[kind]).elements:
            r = Row(el)
            if r['charaParamId']:
                out[r['charaParamId']] = self._spirit_stock(r)
        return out

    @staticmethod
    def _spirit_stock(r: Row) -> List[int]:
        d = r.f['stockNum'].data
        return list(struct.unpack(f'<{len(d) // 2}H', d))

    def set_spirit(self, kind: str, param_id: int, count: int, tier: int = 0):
        array = SPIRIT_ARRAY[kind]
        arr = l5bin.find(self._spirit_root(), array)
        rows = [Row(el) for el in arr.elements]
        for r in rows:
            if r['charaParamId'] == param_id:
                self._write_spirit_stock(r, count, tier)
                return
        free = next((i for i, r in enumerate(rows) if r['charaParamId'] == 0), None)
        if free is None:
            raise ValueError(f'{array}: no free slots')
        r = rows[free]
        order = l5bin.find(self._spirit_root(), 'getOrderCount')
        _set(order, _int(order) + 1)
        r['handle'] = slot_handle(free, SPIRIT_HANDLE[array], 0)
        r['getOrder'] = _int(order)
        r['charaParamId'] = param_id
        self._write_spirit_stock(r, count, tier)

    @staticmethod
    def _write_spirit_stock(r: Row, count: int, tier: int):
        # one u16 per spirit tier (normal spirits have 6, hero/basara 1)
        d = r.f['stockNum'].data
        journal.touch(d)
        struct.pack_into('<H', d, 2 * tier, min(count, 0xFFFF))
        if count and 'newFlag' in r:  # newFlag is a bit per tier ("new" badge)
            r['newFlag'] = r['newFlag'] | (1 << tier if len(d) > 2 else 1)

    # ---------------------------------------------------------------- chronicle
    def _chronicle_flags(self):
        g = lambda n: self.save.get(FLAG_SECTION, f'm_Permanent/m_globalChronicle{n}StatusFlag').data
        return g('Clear'), g('Lock'), g('New')

    def chronicle_cleared(self, flag_index: int) -> int:
        """Highest consecutive difficulty cleared (0 = none)."""
        clear = self._chronicle_flags()[0][flag_index]
        k = 0
        while clear >> (k + 1) & 1:
            k += 1
        return k

    def set_chronicle(self, flag_index: int, cleared_up_to: int, difficulties: int = 6):
        """Mark difficulties 1..cleared_up_to as beaten and unlock the next one."""
        clear, lock, new = self._chronicle_flags()
        mask = sum(1 << k for k in range(1, difficulties + 1))
        c = sum(1 << k for k in range(1, cleared_up_to + 1))
        unlocked = sum(1 << k for k in range(1, min(cleared_up_to + 1, difficulties) + 1))
        if cleared_up_to == 0:  # keep whether the first difficulty was reachable
            unlocked = ~lock[flag_index] & 0b10
        for buf in (clear, lock, new):
            journal.touch(buf)
        clear[flag_index] = (clear[flag_index] & ~mask) | c
        lock[flag_index] = (lock[flag_index] & ~mask) | (mask & ~unlocked)
        new[flag_index] &= ~mask

    def open_chronicle_routes(self, board) -> int:
        """Unlock the squares that follow beaten matches, as the game does on a first win.

        ``board`` is ``Catalog.chronicle_board``. Matches pass on the route
        difficulties they have cleared, other squares (paths, route starts) the
        ones they have open. Only ever unlocks; returns how many squares changed.
        """
        from .catalog import CHRONICLE_ROUTE_BITS
        clear, lock, new = self._chronicle_flags()
        journal.touch(lock)
        journal.touch(new)
        changed, todo = set(), list(board)
        while todo:
            f = todo.pop()
            is_match, targets = board[f]
            opened = (clear[f] if is_match else ~lock[f]) & CHRONICLE_ROUTE_BITS
            for t in targets:
                if t < len(lock) and lock[t] & opened:
                    new[t] |= lock[t] & opened
                    lock[t] &= ~opened
                    changed.add(t)
                    todo.append(t)
        return len(changed)

    # ---------------------------------------------------------------- misc
    def token_spirits(self) -> int:
        """Stock of the "ficha" spirit (tokenSpiritInfo)."""
        return Row(l5bin.find(self._spirit_root(), 'tokenSpiritInfo').items)['stockNum']

    def set_token_spirits(self, n: int):
        Row(l5bin.find(self._spirit_root(), 'tokenSpiritInfo').items)['stockNum'] = n

    def _chara_flags(self, name):
        return self.save.get(FLAG_SECTION, f'm_Permanent/m_globalChr{name}Flag').data

    def known_characters(self, indices) -> int:
        met = self._chara_flags('Met')
        return sum(met[i >> 3] >> (i & 7) & 1 for i in indices if i < len(met) * 8)

    def mark_characters_known(self, indices):
        """Set the database "met" bit (character known) for the given flag indices."""
        met = self._chara_flags('Met')
        journal.touch(met)
        for i in indices:
            if i < len(met) * 8:
                met[i >> 3] |= 1 << (i & 7)
