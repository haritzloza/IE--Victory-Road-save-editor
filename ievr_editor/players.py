"""Players (the user's squad) in save section 0x05.

Recruited players live in ``m_saveHumanP`` as a struct of arrays (6000 slots,
one value per slot in each field); per-player structs (equipment, equipped
techniques) are arrays with one element per slot. Created characters such as
the avatar live in ``m_stEditP`` as one struct each with the same fields.
"""
import struct
from typing import List, Optional, Tuple

from . import journal, l5bin
from .editor import INVENTORY_HANDLE, Editor, Row, slot_handle

PLAYER_SECTION = 0x05
MAX_LEVEL = 99

# equip_inv_info field -> inventory array
EQUIP_SLOTS = [('shoes', 'invShoes', 'Botas'), ('misanga', 'invMisanga', 'Pulsera'),
               ('pendant', 'invAccessory', 'Accesorio'), ('special', 'invSpecial', 'Especial'),
               ('costume', 'invCostume', 'Ropa')]
# skillEquipInvInfo fields (all point into invSkill)
SKILL_SLOTS = [(f'specialSkill_{i}', f'Técnica {i + 1}') for i in range(9)] + \
              [('sixSense', 'Sexto sentido'), ('keshinArmed', 'Armadura keshin 1'),
               ('keshinArmed_1', 'Armadura keshin 2'), ('keshinArmed_2', 'Armadura keshin 3')]

_HANDLE_ARRAY = {v: k for k, v in INVENTORY_HANDLE.items()}


def decode_handle(h: int) -> Optional[Tuple[str, int]]:
    """(inventory array, slot index) of an item handle, or None for an empty slot."""
    if not h:
        return None
    low, high = h & 0xFFFF, h >> 16
    idx = (low & 0xFF) | ((low >> 8) & 0x1F) << 8
    array = _HANDLE_ARRAY.get(((low >> 8) & 0xE0, high & 3))
    if array is None or slot_handle(idx, *INVENTORY_HANDLE[array]) != h:
        return None
    return array, idx


class Player:
    """One squad member; ``slot`` indexes m_saveHumanP, ``edit`` indexes m_stEditP."""

    def __init__(self, root, slot: int = None, edit: int = None):
        self.slot, self.edit = slot, edit
        if edit is not None:
            self._items = l5bin.find(root, 'm_stEditP').elements[edit]
        else:
            self._soa = {it.name: it for it in l5bin.find(root, 'm_saveHumanP').items}
            self._items = None

    # scalar fields -------------------------------------------------------
    def _value(self, name):
        if self._items is not None:
            v = l5bin.find(self._items, name)
            return v.data, 0, len(v.data)
        v = self._soa[name]
        slots = len(self._soa['nowLv'].data) // 2  # nowLv is one u16 per slot
        size = len(v.data) // slots
        return v.data, self.slot * size, size

    def get(self, name) -> int:
        data, off, size = self._value(name)
        return int.from_bytes(data[off:off + size], 'little')

    def set(self, name, n: int):
        data, off, size = self._value(name)
        journal.touch(data)
        data[off:off + size] = n.to_bytes(size, 'little')

    @property
    def param_id(self):
        return self.get('param_id_crc')

    @property
    def is_avatar(self):
        return self.edit is not None

    # per-player structs ----------------------------------------------------
    def _struct(self, name) -> Row:
        if self._items is not None:
            return Row(l5bin.find(self._items, name).items)
        return Row(self._soa[name].elements[self.slot])

    def equipment(self) -> Row:
        return self._struct('equip_inv_info')

    def techniques(self) -> Row:
        return self._struct('skillEquipInvInfo')

    def learned_skills(self) -> List[int]:
        """Innate technique ids (skill_list)."""
        arr = l5bin.find(self._items, 'skill_list') if self._items is not None \
            else self._soa['skill_list'].elements[self.slot][0]
        return [Row(el)['id_crc'] for el in arr.elements if Row(el)['id_crc']]

    def name_fields(self):
        return {k: l5bin.find(self._items, k) for k in ('chrName', 'chrNickName', 'uniformName')} \
            if self._items is not None else {}


class Squad:
    def __init__(self, editor: Editor):
        self.editor = editor
        self.root = l5bin.find(editor.save.section(PLAYER_SECTION).items, 'm_Permanent').items

    def players(self) -> List[Player]:
        out = []
        hp = {it.name: it for it in l5bin.find(self.root, 'm_saveHumanP').items}
        ids = struct.unpack(f'<{len(hp["param_id_crc"].data) // 4}I', hp['param_id_crc'].data)
        out += [Player(self.root, slot=i) for i, p in enumerate(ids) if p]
        for i, el in enumerate(l5bin.find(self.root, 'm_stEditP').elements):
            if Row(el)['param_id_crc'] and l5bin.find(el, 'chrName').data[:1] not in (b'\0', b''):
                out.insert(0, Player(self.root, edit=i))
        return out

    # level / rarity --------------------------------------------------------
    @staticmethod
    def set_level(p: Player, level: int):
        level = max(1, min(MAX_LEVEL, level))
        if p.get('nowLv') != level:
            p.set('nowLv', level)
            p.set('nowExp', 0)  # experience is counted within the current level

    @staticmethod
    def set_rarity(p: Player, rarity: int):
        if p.get('charaRarity') != rarity:
            p.set('charaRarity', rarity)
            p.set('nowRarityExp', 0)

    # equipment ---------------------------------------------------------------
    def _inv_row(self, array, idx) -> Row:
        return Row(self.editor._inv_array(array).elements[idx])

    def equipped_item(self, handle: int) -> Optional[int]:
        """item_id an equipment/technique handle points to."""
        loc = decode_handle(handle)
        return self._inv_row(*loc)['item_id'] if loc else None

    def _slot_for(self, array, item_id) -> int:
        """Inventory slot holding item_id (added with 1 unit if not owned)."""
        for i, el in enumerate(self.editor._inv_array(array).elements):
            if Row(el)['item_id'] == item_id:
                return i
        return self.editor.set_item(array, item_id, 1).index

    def _equip(self, row: Row, field: str, array: str, item_id: Optional[int]):
        old = decode_handle(row[field])
        if old:
            r = self._inv_row(*old)
            r['equipment_num'] = max(0, r['equipment_num'] - 1)
        if not item_id:
            row[field] = 0
            return
        idx = self._slot_for(array, item_id)
        r = self._inv_row(array, idx)
        r['equipment_num'] = r['equipment_num'] + 1
        if r['stockNum'] < r['equipment_num']:  # every equipped copy must be owned
            r['stockNum'] = r['equipment_num']
        if r['attr'] != 3:
            r['attr'], r['flag'] = 3, 2
        row[field] = slot_handle(idx, *INVENTORY_HANDLE[array])

    def set_equipment(self, p: Player, field: str, item_id: Optional[int]):
        array = next(a for f, a, _ in EQUIP_SLOTS if f == field)
        self._equip(p.equipment(), field, array, item_id)

    def set_technique(self, p: Player, field: str, item_id: Optional[int]):
        self._equip(p.techniques(), field, 'invSkill', item_id)

    # avatar ------------------------------------------------------------------
    def rename(self, old_name: str, name: str, nickname: str):
        """Rename a created character everywhere its name is stored."""
        def put(v, s):
            b = s.encode()[:len(v.data) - 1]
            journal.touch(v.data)
            v.data[:] = b + bytes(len(v.data) - len(b))
        targets = []
        for el in l5bin.find(self.root, 'm_stEditP').elements:
            targets.append({k: l5bin.find(el, k) for k in ('chrName', 'chrNickName', 'uniformName')})
        edit_root = l5bin.find(self.editor.save.section(0x13).items, 'm_Permanent').items
        for el in l5bin.find(edit_root, 'charaEditStatus').elements:
            names = l5bin.find(el, 'editName').items
            targets.append({k: l5bin.find(names, k) for k in ('chrName', 'chrNickName', 'uniformName')})
        for t in targets:
            if t['chrName'].data.split(b'\0')[0].decode(errors='replace') == old_name:
                put(t['chrName'], name)
                put(t['chrNickName'], nickname)
                put(t['uniformName'], nickname)


# ---------------------------------------------------------------- training
# abilityLearningBoardInfo keeps three training slots per player: the bean
# kind (0-6, tr000001..tr000007; 0xFFFF = slot not opened yet) and how many
# beans were invested. The game caps each slot at 2 * level - 18.
NO_BEAN = 0xFFFF


def training_cap(level: int) -> int:
    return max(0, 2 * level - 18)


def training(p: Player):
    """[(bean kind or None, beans)] for the three training slots."""
    b = p._struct('abilityLearningBoardInfo')
    kinds = struct.unpack('<3H', b.f['trainingBeansType'].data)
    nums = struct.unpack('<3H', b.f['trainingBeansNum'].data)
    return [(None if k == NO_BEAN else k, n) for k, n in zip(kinds, nums)]


def set_training(p: Player, slot: int, beans: int):
    """Set the beans of an opened slot (clamped to the level cap)."""
    b = p._struct('abilityLearningBoardInfo')
    if struct.unpack_from('<H', b.f['trainingBeansType'].data, 2 * slot)[0] == NO_BEAN:
        return
    d = b.f['trainingBeansNum'].data
    journal.touch(d)
    struct.pack_into('<H', d, 2 * slot, max(0, min(beans, training_cap(p.get('nowLv')))))


# Bean kinds of the three slots by main position (1 GK, 2 FW, 3 MF, 4 DF), as
# found on every trained player; kinds index tr000001..tr000007.
BEANS_BY_POSITION = {1: (6, 4, 3), 2: (0, 1, 2), 3: (2, 1, 5), 4: (5, 3, 4)}


def open_training(p: Player, position: int) -> bool:
    """Give a never-trained player the bean slots of their position."""
    kinds = BEANS_BY_POSITION.get(position)
    if not kinds or any(k is not None for k, _ in training(p)):
        return False
    d = p._struct('abilityLearningBoardInfo').f['trainingBeansType'].data
    journal.touch(d)
    d[:] = struct.pack('<3H', *kinds)
    return True


def max_training(p: Player, position: int = None):
    """Fill every training slot up to the level cap (opening them if the position is known)."""
    if position is not None:
        open_training(p, position)
    for slot, (kind, _) in enumerate(training(p)):
        if kind is not None:
            set_training(p, slot, training_cap(p.get('nowLv')))
