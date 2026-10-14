"""Read files out of the game's encrypted CRI CPK archives.

Each ``data/packs/<md5>.cpk`` is XOR'd with the same keystream as the saves,
seeded with ``crc32(cpk_file_name)``. Underneath is a standard CRI CPK.
"""
import struct
import zlib
from pathlib import Path

from . import crypto


class _EncFile:
    def __init__(self, path: Path):
        self.f = open(path, 'rb')
        self.seed = zlib.crc32(path.name.encode())

    def read(self, offset: int, size: int) -> bytes:
        self.f.seek(offset)
        return crypto.xor(self.f.read(size), self.seed, offset)

    def close(self):
        self.f.close()


def _utf_unmask(b: bytes) -> bytes:
    out = bytearray(b)
    m = 0x655F
    for i in range(len(out)):
        out[i] ^= m & 0xFF
        m = (m * 0x4115) & 0xFFFFFFFF
    return bytes(out)


def parse_utf(b: bytes) -> list:
    """Parse a CRI @UTF table into a list of row dicts."""
    if b[:4] != b'@UTF':
        b = _utf_unmask(b)
        if b[:4] != b'@UTF':
            raise ValueError('not a @UTF table')
    base = 8
    _, rows_off, str_off, data_off, _, ncols, row_len, nrows = struct.unpack_from('>HHIIIHHI', b, base)
    rows_off += base
    str_off += base
    data_off += base

    def string(o):
        s = str_off + o
        return b[s:b.index(b'\0', s)].decode('utf-8', 'replace')

    fmt = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i', 6: 'Q', 7: 'q', 8: 'f'}

    def read_val(typ, pos):
        if typ in fmt:
            v = struct.unpack_from('>' + fmt[typ], b, pos)[0]
            return v, struct.calcsize(fmt[typ])
        if typ == 0xA:
            return string(struct.unpack_from('>I', b, pos)[0]), 4
        if typ == 0xB:
            o, n = struct.unpack_from('>II', b, pos)
            return b[data_off + o:data_off + o + n], 8
        raise ValueError(f'utf type {typ:#x}')

    cols = []
    pos = base + 24
    for _ in range(ncols):
        flags = b[pos]
        name = string(struct.unpack_from('>I', b, pos + 1)[0])
        pos += 5
        storage, typ = flags & 0xF0, flags & 0x0F
        const = None
        if storage == 0x30:
            const, n = read_val(typ, pos)
            pos += n
        cols.append((name, storage, typ, const))

    rows = []
    for r in range(nrows):
        p = rows_off + r * row_len
        row = {}
        for name, storage, typ, const in cols:
            if storage == 0x50:
                row[name], n = read_val(typ, p)
                p += n
            elif storage == 0x30:
                row[name] = const
            else:
                row[name] = None
        rows.append(row)
    return rows


def crilayla_decompress(src: bytes) -> bytes:
    """CRILAYLA: LZ variant decoded backwards; a raw 0x100-byte prefix trails the stream."""
    if src[:8] != b'CRILAYLA':
        return src
    usize, csize = struct.unpack_from('<II', src, 8)
    out = bytearray(0x100 + usize)
    out[:0x100] = src[0x10 + csize:0x10 + csize + 0x100]
    # Bits are consumed MSB-first from the end of the compressed block backwards;
    # reverse once so they can be read with a forward cursor.
    r = src[0x10:0x10 + csize][::-1] + b'\0\0\0'
    pos = 0

    def bits(n):
        nonlocal pos
        i = pos >> 3
        v = (r[i] << 16 | r[i + 1] << 8 | r[i + 2]) >> (24 - (pos & 7) - n)
        pos += n
        return v & ((1 << n) - 1)

    dst = 0x100 + usize - 1
    while dst >= 0x100:
        if bits(1):
            back = bits(13) + 3
            length = 3
            for width in (2, 3, 5, 8):
                v = bits(width)
                length += v
                if v != (1 << width) - 1:
                    break
            else:
                while True:
                    v = bits(8)
                    length += v
                    if v != 0xFF:
                        break
            for _ in range(length):
                out[dst] = out[dst + back]
                dst -= 1
        else:
            out[dst] = bits(8)
            dst -= 1
    return bytes(out)


class Cpk:
    def __init__(self, path):
        self.path = Path(path)
        self.f = _EncFile(self.path)
        hdr = self.f.read(0, 0x10)
        if hdr[:4] != b'CPK ':
            raise ValueError(f'{self.path.name}: not a CPK after decryption')
        size = struct.unpack_from('<Q', hdr, 8)[0]
        self.header = parse_utf(self.f.read(0x10, size))[0]
        toc_off = self.header['TocOffset']
        toc_size = self.header['TocSize']
        content = self.header.get('ContentOffset') or toc_off
        self.add_offset = min(toc_off, content)
        toc = self.f.read(toc_off, toc_size)
        self.files = {}
        for row in parse_utf(toc[0x10:]):
            name = (row['DirName'] + '/' if row.get('DirName') else '') + row['FileName']
            self.files[name] = row

    def read(self, name: str) -> bytes:
        row = self.files[name]
        data = self.f.read(row['FileOffset'] + self.add_offset, row['FileSize'])
        if row['ExtractSize'] and row['ExtractSize'] != row['FileSize']:
            data = crilayla_decompress(data)
        return data

    def close(self):
        self.f.close()
