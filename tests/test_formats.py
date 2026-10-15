"""Format tests on synthetic data (no game files or real saves needed)."""
import struct
import zlib

import pytest

from ievr_editor import container, crypto, l5bin, t2b
from ievr_editor.editor import INVENTORY_HANDLE, Editor, slot_handle
from ievr_editor.players import decode_handle


# ---------------------------------------------------------------- crypto

def test_xor_roundtrip():
    data = bytes(range(256)) * 40
    enc = crypto.xor(data, 0x12345678)
    assert enc != data
    assert crypto.xor(enc, 0x12345678) == data


@pytest.mark.parametrize('offset', [0, 1, 3, 4, 1021, 4096])
def test_keystream_offset_matches_full_stream(offset):
    full = crypto.keystream(0xCAFEBABE, offset + 300)
    assert (crypto.keystream(0xCAFEBABE, 300, offset) == full[offset:]).all()


def test_keystream_matches_reference_byte_loop():
    """Vectorised keystream == straightforward port of the game's routine."""
    seed = 0x8A90ABA9
    sb = struct.pack('<I', seed)
    ref = bytearray()
    for pos in range(64):
        crc = zlib.crc32(sb, pos & ~3)
        r = (pos & 3) * 2
        k = (((crc >> r) & 0xFF) << 2) & 0xFF | ((crc >> (r + 8)) & 3)
        k = ((k << 2) & 0xFF) | ((crc >> (r + 16)) & 3)
        k = ((k << 2) & 0xFF) | ((crc >> (r + 24)) & 3)
        ref.append(k)
    assert bytes(crypto.keystream(seed, 64)) == bytes(ref)


@pytest.mark.parametrize('seed', [0, 1, 0x4EAD4023, 0xFFFFFFFF])
def test_recover_seed(seed):
    plain = struct.pack('<I', container.MAGIC) + b'rest of the file'
    assert crypto.recover_seed(crypto.xor(plain, seed), container.MAGIC) == seed


# ---------------------------------------------------------------- container

def make_container(seed=0x1234ABCD):
    hdr = bytearray(container.HEADER_SIZE)
    struct.pack_into('<IIQ', hdr, 0, container.MAGIC, 0, 0x3EBE198A)
    hdr[0x10:0x10 + 14] = b'TEST-USERDATAL'
    c = container.Container(seed, hdr, [container.Entry('AUTOSAVE_data.bin', b'A' * 1000),
                                        container.Entry('HEADERSAVE_data.bin', b'hdr')])
    for i, e in enumerate(c.entries):
        o = container.ENTRY_OFF + i * container.ENTRY_SIZE
        hdr[o + 0xC:o + 0xC + len(e.name)] = e.name.encode()
    return c


def test_container_roundtrip():
    raw = make_container().dump()
    c = container.Container.load(raw)
    assert c.seed == 0x1234ABCD
    assert c.owner_id == 0x3EBE198A
    assert [e.name for e in c.entries] == ['AUTOSAVE_data.bin', 'HEADERSAVE_data.bin']
    assert c.entry('AUTOSAVE_data.bin').data == b'A' * 1000
    assert c.dump() == raw


def test_container_detects_corruption():
    raw = bytearray(make_container().dump())
    raw[0x900] ^= 0xFF  # inside the first blob
    with pytest.raises(ValueError):
        container.Container.load(bytes(raw))


# ---------------------------------------------------------------- l5bin

def h(name):
    return zlib.crc32(name.encode())


def sample_tree():
    V = lambda n, d: l5bin.Value(h(n), bytearray(d))
    inner = [l5bin.Array(h('skill_list'), [[V('id_crc', b'\1\2\3\4')], [V('id_crc', b'\0\0\0\0')]])]
    return [l5bin.Section(0x01, [l5bin.Struct(h('m_Permanent'), [
        V('money', b'\x10\x00\x00\x00'),
        # 2D array whose rows share the outer array's name (as skill_list does in saves)
        l5bin.Array(h('skill_list'), [inner, inner]),
        l5bin.Array(h('invConsume'), [[V('item_id', b'\xaa' * 4), V('stockNum', b'\5\0\0\0')]] * 3),
    ])]), l5bin.Section(0x02, [V('flags', b'\0' * 16)])]


def test_l5bin_roundtrip():
    blob = l5bin.serialize(sample_tree())
    assert l5bin.serialize(l5bin.parse(blob)) == blob


def test_l5bin_nested_same_name_arrays():
    secs = l5bin.parse(l5bin.serialize(sample_tree()))
    outer = secs[0].items[0].items[1]  # m_Permanent/skill_list
    assert len(outer.elements) == 2
    assert len(outer.elements[0][0].elements) == 2


def test_l5bin_rejects_bad_trailer():
    blob = bytearray(l5bin.serialize(sample_tree()))
    blob[-1] ^= 1
    with pytest.raises(ValueError):
        l5bin.parse(bytes(blob))


# ---------------------------------------------------------------- t2b

def test_t2b_rejects_other_formats():
    with pytest.raises(ValueError):
        t2b.parse(b'RDBN' + bytes(60))


# ---------------------------------------------------------------- handles

@pytest.mark.parametrize('array', sorted(INVENTORY_HANDLE))
@pytest.mark.parametrize('index', [0, 1, 0x1C, 0x139, 0x289, 3199])
def test_handle_roundtrip(array, index):
    assert decode_handle(slot_handle(index, *INVENTORY_HANDLE[array])) == (array, index)


def test_handle_matches_game_examples():
    # handles copied from a real save
    assert slot_handle(0, *INVENTORY_HANDLE['invConsume']) == 0x00040000
    assert slot_handle(0x1C, *INVENTORY_HANDLE['invShoes']) == 0x0074201C
    assert slot_handle(0x289, *INVENTORY_HANDLE['invSkill']) == 0x0A296289
    assert decode_handle(0) is None


# ---------------------------------------------------------------- chronicle

class FakeEditor(Editor):
    def __init__(self):
        self.flags = (bytearray(4), bytearray(b'\x7e' * 4), bytearray(4))

    def _chronicle_flags(self):
        return self.flags


@pytest.mark.parametrize('k,clear,lock', [(0, 0x00, 0x7E), (1, 0x02, 0x78), (2, 0x06, 0x70),
                                          (5, 0x3E, 0x00), (6, 0x7E, 0x00)])
def test_chronicle_bits(k, clear, lock):
    e = FakeEditor()
    e.set_chronicle(1, k)
    assert e.chronicle_cleared(1) == k
    assert e.flags[0][1] == clear
    assert e.flags[1][1] == lock
    assert e.flags[0][0] == 0 and e.flags[1][0] == 0x7E  # other pieces untouched


def test_chronicle_routes_open_following_squares():
    # 0 match -> 1 path square -> 2 match ; 2 -> 3 route start (non-match) -> 4 match ; 5 unrelated
    board = {0: (True, [1, 2]), 1: (False, []), 2: (True, [3]), 3: (False, [4]), 4: (True, []), 5: (True, [])}
    e = FakeEditor()
    e.flags = (bytearray(6), bytearray(b'\x7e' * 6), bytearray(6))
    e.set_chronicle(0, 6)
    assert e.open_chronicle_routes(board) == 2
    clear, lock, new = e.flags
    assert lock[1] == lock[2] == 0x78 and new[2] == 0x06   # only crónica + desbloqueo de ruta propagate
    assert lock[3] == lock[4] == lock[5] == 0x7E           # 2 not beaten yet
    e.set_chronicle(2, 1)
    assert e.open_chronicle_routes(board) == 2
    assert lock[2] == 0x78                                  # own next difficulty (2) stays open
    assert lock[3] == 0x7C and lock[4] == 0x7C              # cascades through the non-match square
    assert e.open_chronicle_routes(board) == 0              # idempotent, never relocks
