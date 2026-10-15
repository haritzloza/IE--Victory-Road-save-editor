"""Editing operations on a small synthetic save (same structures as the real one)."""
import struct
import zlib

import pytest

from ievr_editor import journal, l5bin
from ievr_editor.editor import INVENTORY_HANDLE, Editor, Row, slot_handle
from ievr_editor.journal import Journal
from ievr_editor.players import (Squad, decode_handle, max_training, open_training, set_training, training,
                                 training_cap)

SLOTS = 8  # player slots (6000 in the game)


def V(name, data):
    return l5bin.Value(zlib.crc32(name.encode()), bytearray(data))


def S(name, items):
    return l5bin.Struct(zlib.crc32(name.encode()), items)


def A(name, elements):
    return l5bin.Array(zlib.crc32(name.encode()), elements)


def inv_slot(extra=()):
    base = [V('handle', bytes(4)), V('item_id', bytes(4)), V('get_order', bytes(4)), V('attr', b'\0'),
            V('flag', b'\0'), V('stockNum', bytes(4))]
    return base + [V(n, bytes(sz)) for n, sz in extra]


EQUIPABLE = (('equipment_num', 4), ('is_lock', 1))


def spirit_slot(normal=True):
    if normal:
        return [V('handle', bytes(4)), V('getOrder', bytes(4)), V('reserve', bytes(2)),
                V('charaParamId', bytes(4)), V('newFlag', bytes(4)), V('stockNum', bytes(12)),
                V('usedStockNum', bytes(12))]
    return [V('handle', bytes(4)), V('getOrder', bytes(4)), V('reserve', b'\0'), V('charaParamId', bytes(4)),
            V('stockNum', bytes(2)), V('usedStockNum', bytes(2)), V('newFlag', b'\0'), V('reserve', b'\0')]


def player_structs():
    return {
        'equip_inv_info': [V(n, bytes(4)) for n in ('shoes', 'misanga', 'pendant', 'special', 'costume')],
        'skillEquipInvInfo': [V(f'specialSkill_{i}', bytes(4)) for i in range(9)] +
                             [V(n, bytes(4)) for n in ('sixSense', 'keshinArmed', 'keshinArmed_1', 'keshinArmed_2')],
        'abilityLearningBoardInfo': [V('trainingBeansType', struct.pack('<3H', *[0xFFFF] * 3)),
                                     V('trainingBeansNum', bytes(6)), V('playCount', bytes(2))],
    }


def build_save():
    human = [V('handle', bytes(4 * SLOTS)),
             V('param_id_crc', struct.pack(f'<{SLOTS}I', 0x111, 0x222, *[0] * (SLOTS - 2))),
             V('nowExp', struct.pack(f'<{SLOTS}I', 50, 0, *[0] * (SLOTS - 2))),
             V('nowLv', struct.pack(f'<{SLOTS}H', 40, 10, *[0] * (SLOTS - 2))),
             V('charaRarity', bytes(4 * SLOTS)), V('nowRarityExp', bytes(4 * SLOTS))]
    for name, fields in player_structs().items():
        human.append(A(name, [[V(f.name if isinstance(f, l5bin.Value) else f, bytes(f.data)) for f in fields]
                              for _ in range(SLOTS)]))
    avatar = [V('param_id_crc', struct.pack('<I', 0x999)), V('nowExp', bytes(4)), V('nowLv', struct.pack('<H', 20)),
              V('charaRarity', bytes(4)), V('nowRarityExp', bytes(4))]
    avatar += [S(n, [V(f.name, bytes(f.data)) for f in fs]) for n, fs in player_structs().items()]
    avatar += [V('chrName', b'Haritz'.ljust(48, b'\0')), V('chrNickName', b'Loza'.ljust(48, b'\0')),
               V('uniformName', b'Loza'.ljust(48, b'\0')), V('mainPosition', b'\x02')]
    empty_edit = [V('param_id_crc', bytes(4)), V('chrName', bytes(48)), V('chrNickName', bytes(48)),
                  V('uniformName', bytes(48))]
    sections = {
        0x02: [S('m_Permanent', [V('m_globalChronicleClearStatusFlag', bytes(8)),
                                 V('m_globalChronicleLockStatusFlag', b'\x7e' * 8),
                                 V('m_globalChronicleNewStatusFlag', bytes(8)),
                                 V('m_globalChrMetFlag', bytes(4))])],
        0x04: [A('invConsume', [inv_slot() for _ in range(3)]),
               A('invShoes', [inv_slot(EQUIPABLE) for _ in range(3)]),
               A('invSkill', [inv_slot(EQUIPABLE) for _ in range(3)]),
               V('m_get_order_count', struct.pack('<I', 100))],
        0x05: [S('m_Permanent', [S('m_saveHumanP', human), A('m_stEditP', [empty_edit, avatar])])],
        0x12: [S('m_Permanent', [A('normalSpiritInfo', [spirit_slot() for _ in range(3)]),
                                 A('heroSpiritInfo', [spirit_slot(False) for _ in range(2)]),
                                 A('basaraSpiritInfo', [spirit_slot(False) for _ in range(2)]),
                                 S('tokenSpiritInfo', [V('handle', bytes(4)), V('stockNum', struct.pack('<I', 11))]),
                                 V('getOrderCount', struct.pack('<I', 7))])],
        0x13: [S('m_Permanent', [A('charaEditStatus', [[S('editName', [
            V('chrName', b'Haritz'.ljust(48, b'\0')), V('chrNickName', b'Loza'.ljust(48, b'\0')),
            V('uniformName', b'Loza'.ljust(48, b'\0'))])]])])],
    }
    return FakeSave({sid: l5bin.Section(sid, items) for sid, items in sections.items()})


class FakeSave:
    def __init__(self, sections):
        self.secs = sections

    def section(self, sid, entry='AUTOSAVE_data.bin'):
        return self.secs[sid]

    def get(self, sid, path, entry='AUTOSAVE_data.bin'):
        return l5bin.get(self.secs[sid].items, path)

    def snapshot(self):
        return l5bin.serialize([self.secs[k] for k in sorted(self.secs)])


@pytest.fixture
def ed():
    journal._active = None
    return Editor(build_save())


def test_fake_save_serializes(ed):
    assert l5bin.serialize(l5bin.parse(ed.save.snapshot())) == ed.save.snapshot()


# ---------------------------------------------------------------- inventory

def test_add_new_item_uses_free_slot_handle_and_order(ed):
    e = ed.set_item('invConsume', 0xAAAA, 5)
    assert e.index == 0
    r = Row(ed._inv_array('invConsume').elements[0])
    assert r['item_id'] == 0xAAAA and r['stockNum'] == 5
    assert r['handle'] == slot_handle(0, *INVENTORY_HANDLE['invConsume'])
    assert (r['attr'], r['flag']) == (3, 2)
    assert r['get_order'] == 101
    assert ed.set_item('invConsume', 0xBBBB, 1).index == 1
    assert Row(ed._inv_array('invConsume').elements[1])['get_order'] == 102


def test_existing_item_only_changes_stock(ed):
    ed.set_item('invConsume', 0xAAAA, 5)
    ed.set_item('invConsume', 0xAAAA, 9)
    assert ed.owned_items() == {0xAAAA: 9}
    assert Row(ed._inv_array('invConsume').elements[1])['item_id'] == 0


def test_inventory_full(ed):
    for i in range(3):
        ed.set_item('invConsume', 0x100 + i, 1)
    with pytest.raises(ValueError):
        ed.set_item('invConsume', 0x999, 1)


def test_stock_never_below_equipped(ed):
    ed.set_item('invShoes', 0xB007, 1)
    Row(ed._inv_array('invShoes').elements[0])['equipment_num'] = 3
    ed.set_item('invShoes', 0xB007, 1)
    assert ed.owned_items()[0xB007] == 3


# ---------------------------------------------------------------- spirits

def test_spirit_tiers_and_new_flag(ed):
    ed.set_spirit('normal', 0x5151, 4, tier=1)
    assert ed.spirits('normal')[0x5151] == [0, 4, 0, 0, 0, 0]
    r = Row(l5bin.find(ed._spirit_root(), 'normalSpiritInfo').elements[0])
    assert r['newFlag'] == 0b10 and r['getOrder'] == 8
    ed.set_spirit('hero', 0x4242, 2)
    assert ed.spirits('hero')[0x4242] == [2]


def test_token_spirits(ed):
    assert ed.token_spirits() == 11
    ed.set_token_spirits(40)
    assert ed.token_spirits() == 40


def test_mark_characters_known(ed):
    ed.mark_characters_known({0, 9, 31, 500})  # 500 is out of range and ignored
    assert ed.known_characters({0, 9, 31, 1}) == 3


# ---------------------------------------------------------------- players

def test_squad_lists_players_and_avatar(ed):
    ps = Squad(ed).players()
    assert ps[0].is_avatar and ps[0].param_id == 0x999
    assert [p.param_id for p in ps[1:]] == [0x111, 0x222]


def test_level_and_rarity(ed):
    p = Squad(ed).players()[1]
    Squad.set_level(p, 120)
    assert p.get('nowLv') == 99 and p.get('nowExp') == 0
    Squad.set_rarity(p, 4)
    assert p.get('charaRarity') == 4
    # the neighbouring slot of the struct-of-arrays is untouched
    assert Squad(ed).players()[2].get('nowLv') == 10


def test_equip_adds_item_and_counts(ed):
    sq = Squad(ed)
    p = sq.players()[1]
    sq.set_equipment(p, 'shoes', 0xB007)
    h = p.equipment()['shoes']
    assert decode_handle(h) == ('invShoes', 0)
    r = Row(ed._inv_array('invShoes').elements[0])
    assert (r['item_id'], r['stockNum'], r['equipment_num']) == (0xB007, 1, 1)
    sq.set_equipment(sq.players()[2], 'shoes', 0xB007)  # a second player: stock grows with it
    assert (r['stockNum'], r['equipment_num']) == (2, 2)
    sq.set_equipment(p, 'shoes', None)
    assert p.equipment()['shoes'] == 0 and r['equipment_num'] == 1


def test_equip_technique_on_avatar(ed):
    sq = Squad(ed)
    avatar = sq.players()[0]
    sq.set_technique(avatar, 'specialSkill_0', 0x5C11)
    assert decode_handle(avatar.techniques()['specialSkill_0']) == ('invSkill', 0)


def test_training_cap_and_open_by_position(ed):
    sq = Squad(ed)
    p = sq.players()[1]  # level 40 -> cap 62
    assert training_cap(40) == 62 and training_cap(5) == 0
    assert training(p) == [(None, 0)] * 3
    set_training(p, 0, 10)  # slot not opened: ignored
    assert training(p)[0] == (None, 0)
    assert open_training(p, 4)  # defender
    assert [k for k, _ in training(p)] == [5, 3, 4]
    max_training(p)
    assert training(p) == [(5, 62), (3, 62), (4, 62)]
    set_training(p, 1, 999)
    assert training(p)[1] == (3, 62)


def test_rename_avatar_everywhere(ed):
    sq = Squad(ed)
    sq.rename('Haritz', 'Mark', 'Evans')
    av = sq.players()[0].name_fields()
    assert av['chrName'].data.rstrip(b'\0') == b'Mark' and av['chrNickName'].data.rstrip(b'\0') == b'Evans'
    edit = l5bin.get(ed.save.section(0x13).items, 'm_Permanent/charaEditStatus[0]/editName')
    assert l5bin.find(edit.items, 'chrName').data.rstrip(b'\0') == b'Mark'


# ---------------------------------------------------------------- chronicle + journal

def test_journal_undo_redo_restores_bytes(ed):
    j = Journal()
    j.activate()
    before = ed.save.snapshot()
    sq = Squad(ed)
    with j.action('item'):
        ed.set_item('invConsume', 0xAAAA, 5)
    with j.action('level'):
        Squad.set_level(sq.players()[1], 99)
    with j.action('chronicle'):
        ed.set_chronicle(2, 6)
    with j.action('nothing'):
        ed.set_item('invConsume', 0xAAAA, 5)  # no real change -> no step
    with j.action('training'):
        max_training(sq.players()[2], 2)
    after = ed.save.snapshot()
    assert [s.label for s in j.undo] == ['item', 'level', 'chronicle', 'training']
    assert j.dirty and j.pending() == ['item', 'level', 'chronicle', 'training']
    while j.undo_last():
        pass
    assert ed.save.snapshot() == before and not j.dirty
    while j.redo_last():
        pass
    assert ed.save.snapshot() == after
    j.mark_saved()
    assert not j.dirty and j.pending() == []
    j.undo_last()
    assert j.dirty
    journal._active = None
