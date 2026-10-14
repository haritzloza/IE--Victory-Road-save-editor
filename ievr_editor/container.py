"""Steam save container (002AB8F4-USERDATALIVE / -SYSTEMLIVE).

Layout after removing the keystream (see nie.exe FUN_1404ee1a0 / FUN_1404ee750):

  0x000 u32  magic 0x9DCE66C3
  0x004 u32  crc32(header[0x8:0x800])
  0x008 u64  owner id (checked by the game on load)
  0x010 char filename[0x40]
  0x050 entry[8], 0x80 bytes each:
          u32 crc32(blob), u32 size, u32 offset (relative to 0x800), char name[0x74]
  0x800 blobs
"""
import struct
import zlib
from dataclasses import dataclass, field

from . import crypto

MAGIC = 0x9DCE66C3
HEADER_SIZE = 0x800
ENTRY_OFF = 0x50
ENTRY_SIZE = 0x80
MAX_ENTRIES = 8


@dataclass
class Entry:
    name: str
    data: bytes


@dataclass
class Container:
    seed: int
    header: bytearray            # raw 0x800 header, kept to preserve unknown bytes
    entries: list = field(default_factory=list)

    @property
    def owner_id(self) -> int:
        return struct.unpack_from('<Q', self.header, 8)[0]

    @property
    def filename(self) -> str:
        return self.header[0x10:0x50].split(b'\0')[0].decode()

    def entry(self, name: str) -> Entry:
        for e in self.entries:
            if e.name == name:
                return e
        raise KeyError(name)

    @classmethod
    def load(cls, raw: bytes) -> 'Container':
        seed = crypto.recover_seed(raw, MAGIC)
        plain = crypto.xor(raw, seed)
        hdr = bytearray(plain[:HEADER_SIZE])
        magic, hcrc = struct.unpack_from('<II', hdr)
        if magic != MAGIC or hcrc != zlib.crc32(hdr[8:HEADER_SIZE]):
            raise ValueError('not an IEVR save container (bad magic/header crc)')
        entries = []
        for i in range(MAX_ENTRIES):
            o = ENTRY_OFF + i * ENTRY_SIZE
            crc, size, off = struct.unpack_from('<III', hdr, o)
            if size == 0:
                continue
            name = hdr[o + 0xC:o + ENTRY_SIZE].split(b'\0')[0].decode()
            blob = plain[HEADER_SIZE + off:HEADER_SIZE + off + size]
            if len(blob) != size or zlib.crc32(blob) != crc:
                raise ValueError(f'entry {name}: crc mismatch')
            entries.append(Entry(name, blob))
        return cls(seed, hdr, entries)

    def dump(self) -> bytes:
        hdr = bytearray(self.header)
        if len(self.entries) > MAX_ENTRIES:
            raise ValueError('too many entries')
        body = bytearray()
        for i, e in enumerate(self.entries):
            o = ENTRY_OFF + i * ENTRY_SIZE
            struct.pack_into('<III', hdr, o, zlib.crc32(e.data), len(e.data), len(body))
            body += e.data
        struct.pack_into('<I', hdr, 4, zlib.crc32(hdr[8:HEADER_SIZE]))
        return crypto.xor(bytes(hdr) + bytes(body), self.seed)
