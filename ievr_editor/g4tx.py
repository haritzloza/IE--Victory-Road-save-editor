"""LEVEL-5 G4TX texture archives (PC/DX11 build).

Header (0x60): "G4TX", u16 header size, u16 type, u32, u32 table size, 16 zero
bytes, u16 texture count, u16 total count, u8, u8 sub-texture count, ...
Then 0x30-byte texture entries (u32, u32 data offset, u32 data size, ...,
u16 width, u16 height), 0x18-byte sub entries, crc32 name hashes, ids,
u16 name offsets and the names. Texture data starts at the 16-aligned end of
the table; on PC each texture is a plain DDS file (BC7).
Layout as documented by Kuriimu2's Switch plugin (GPL-3.0).
"""
import struct
from typing import List, Tuple


def textures(data: bytes) -> List[Tuple[str, bytes]]:
    """[(name, dds bytes)] for every texture in the archive."""
    if data[:4] != b'G4TX':
        raise ValueError('not a G4TX file')
    header_size, _, _, table_size = struct.unpack_from('<hhii', data, 4)
    count, total, _, sub = struct.unpack_from('<hhBB', data, 0x20)
    pos = ((0x60 + count * 0x30 + sub * 0x18 + 0xF) & ~0xF) + total * 4  # skip name hashes
    pos = (pos + total + 3) & ~3                                           # skip ids
    name_offsets = struct.unpack_from(f'<{total}h', data, pos)
    base = (header_size + table_size + 0xF) & ~0xF
    out = []
    for i in range(count):
        _, off, size = struct.unpack_from('<iii', data, 0x60 + i * 0x30)
        s = pos + name_offsets[i]
        out.append((data[s:data.index(b'\0', s)].decode('ascii', 'replace'), data[base + off:base + off + size]))
    return out
