"""Level-5 T2B (``.cfg.bin``) tables.

Layout: u32 entry_count, u32 string_offset, u32 string_size, u32 string_count,
then entries ``u32 name_crc, u8 n, packed 2-bit types (aligned to 4), i32 values[n]``,
the string block, and a 16-byte aligned footer (magic 0x62327401 at len-0x10).
Value types: 0 = string offset, 1 = int, 2 = float.
"""
import struct
from dataclasses import dataclass
from typing import List

FOOTER_MAGIC = 0x62327401


@dataclass
class T2bEntry:
    crc: int
    types: List[int]
    raw: List[int]
    values: list
    name: str = ''


def is_t2b(data: bytes) -> bool:
    return len(data) >= 0x10 and struct.unpack_from('<I', data, len(data) - 0x10)[0] == FOOTER_MAGIC


def key_table(data: bytes) -> dict:
    """crc -> entry name, from the key table that follows the string block."""
    _, soff, ssize, _ = struct.unpack_from('<IIII', data)
    k = (soff + ssize + 15) & ~15
    if k + 16 > len(data) - 0x10:
        return {}
    size, count, str_off, str_size = struct.unpack_from('<IIII', data, k)
    names = {}
    for i in range(count):
        crc, o = struct.unpack_from('<II', data, k + 16 + 8 * i)
        s = k + str_off + o
        names[crc] = data[s:data.index(b'\0', s)].decode('utf-8', 'replace')
    return names


def parse(data: bytes) -> List[T2bEntry]:
    if not is_t2b(data):
        raise ValueError('not a T2B table (RDBN files are read with rdbn.parse)')
    count, soff, ssize, _ = struct.unpack_from('<IIII', data)
    strings = data[soff:soff + ssize]
    keys = key_table(data)

    def string_at(o):
        if not 0 <= o < len(strings):
            return None
        return strings[o:strings.index(b'\0', o)].decode('utf-8', 'replace')

    pos = 16
    out = []
    for _ in range(count):
        crc, n = struct.unpack_from('<IB', data, pos)
        pos += 5
        types = []
        for i in range(0, n, 4):
            chunk = data[pos]
            pos += 1
            types += [(chunk >> (2 * j)) & 3 for j in range(min(4, n - i))]
        pos = (pos + 3) & ~3
        raw = list(struct.unpack_from(f'<{n}i', data, pos))
        pos += 4 * n
        vals = []
        for t, v in zip(types, raw):
            if t == 0:
                vals.append(string_at(v))
            elif t == 2:
                vals.append(struct.unpack('<f', struct.pack('<i', v))[0])
            else:
                vals.append(v)
        out.append(T2bEntry(crc, types, raw, vals, keys.get(crc, f'#{crc:08x}')))
    return out
