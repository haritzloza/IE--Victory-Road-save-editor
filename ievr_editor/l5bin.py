"""Level-5 tagged binary tree used inside the save blobs.

A blob is a sequence of sections::

    u8 0xEE, u8 0xFF, u8 section_id, u8 0x10, u32 body_size, body, u32 0x0000EFFF

A body is a sequence of tokens ``u32 name_crc32, u32 info``. ``info >> 24`` is the
kind and the low 24 bits its argument:

    0  value   -> followed by ``arg`` bytes of payload
    1  begin   -> struct start, closed by a kind-2 token with the same hash
    2  end
    3  array   -> ``arg`` elements follow; each element is closed by
                  a kind-4 token with the same hash and the same ``arg``
    4  element end

Parsing is lossless: ``serialize(parse(b)) == b``.
"""
import struct
from dataclasses import dataclass, field
from typing import Iterator, List, Union

from .names import name_of

SECTION_TRAILER = b'\xff\xef\x00\x00'


@dataclass
class Value:
    hash: int
    data: bytearray

    @property
    def name(self) -> str:
        return name_of(self.hash)


@dataclass
class Struct:
    hash: int
    items: List['Item'] = field(default_factory=list)

    @property
    def name(self) -> str:
        return name_of(self.hash)


@dataclass
class Array:
    hash: int
    elements: List[List['Item']] = field(default_factory=list)

    @property
    def name(self) -> str:
        return name_of(self.hash)


Item = Union[Value, Struct, Array]


@dataclass
class Section:
    section_id: int
    items: List[Item]


class _Reader:
    def __init__(self, buf: bytes, pos: int, end: int):
        self.buf, self.pos, self.end = buf, pos, end

    def peek(self):
        h, info = struct.unpack_from('<II', self.buf, self.pos)
        return h, info >> 24, info & 0xFFFFFF

    def items(self, stop) -> List[Item]:
        """Read items until ``stop(hash, kind, arg)`` matches; consumes the stop token."""
        out = []
        while True:
            if self.pos + 8 > self.end:
                if stop is None:
                    return out
                raise ValueError(f'unexpected end of data at {self.pos:#x}')
            h, kind, arg = self.peek()
            if stop is not None and stop(h, kind, arg):
                self.pos += 8
                return out
            self.pos += 8
            if kind == 0:
                out.append(Value(h, bytearray(self.buf[self.pos:self.pos + arg])))
                self.pos += arg
            elif kind == 1:
                out.append(Struct(h, self.items(lambda h2, k2, a2, h=h: k2 == 2 and h2 == h)))
            elif kind == 3:
                arr = Array(h)
                for _ in range(arg):
                    arr.elements.append(
                        self.items(lambda h2, k2, a2, h=h, n=arg: k2 == 4 and h2 == h and a2 == n))
                out.append(arr)
            else:
                raise ValueError(f'unexpected token kind {kind} at {self.pos - 8:#x}')


def parse(blob: bytes) -> List[Section]:
    sections = []
    pos = 0
    while pos < len(blob):
        if blob[pos] != 0xEE or blob[pos + 1] != 0xFF or blob[pos + 3] != 0x10:
            raise ValueError(f'bad section header at {pos:#x}')
        sid = blob[pos + 2]
        size = struct.unpack_from('<I', blob, pos + 4)[0]
        r = _Reader(blob, pos + 8, pos + 8 + size)
        items = r.items(None)
        if r.pos != pos + 8 + size:
            raise ValueError(f'section {sid:#x} did not parse exactly')
        if blob[pos + 8 + size:pos + 12 + size] != SECTION_TRAILER:
            raise ValueError(f'section {sid:#x}: bad trailer')
        sections.append(Section(sid, items))
        pos += 12 + size
    return sections


def _write_items(items: List[Item], out: bytearray):
    for it in items:
        if isinstance(it, Value):
            out += struct.pack('<II', it.hash, len(it.data))
            out += it.data
        elif isinstance(it, Struct):
            out += struct.pack('<II', it.hash, 1 << 24)
            _write_items(it.items, out)
            out += struct.pack('<II', it.hash, 2 << 24)
        else:
            n = len(it.elements)
            out += struct.pack('<II', it.hash, 3 << 24 | n)
            for el in it.elements:
                _write_items(el, out)
                out += struct.pack('<II', it.hash, 4 << 24 | n)


def serialize(sections: List[Section]) -> bytes:
    out = bytearray()
    for s in sections:
        body = bytearray()
        _write_items(s.items, body)
        out += bytes((0xEE, 0xFF, s.section_id, 0x10)) + struct.pack('<I', len(body))
        out += body + SECTION_TRAILER
    return bytes(out)


# ---------------------------------------------------------------- navigation

def find(items: List[Item], name: str) -> Item:
    for it in items:
        if it.name == name:
            return it
    raise KeyError(name)


def get(items: List[Item], path: str) -> Item:
    """Resolve a slash path; ``name[i]`` indexes array elements."""
    cur: Item = None
    scope = items
    for part in path.strip('/').split('/'):
        idx = None
        if part.endswith(']'):
            part, idx = part[:-1].split('[')
            idx = int(idx)
        cur = find(scope, part)
        if idx is not None:
            scope = cur.elements[idx]
            cur = scope
        elif isinstance(cur, Struct):
            scope = cur.items
    return cur


def walk(items: List[Item], prefix: str = '') -> Iterator[tuple]:
    """Yield (path, Value) for every value in the tree."""
    for it in items:
        p = f'{prefix}/{it.name}'
        if isinstance(it, Value):
            yield p, it
        elif isinstance(it, Struct):
            yield from walk(it.items, p)
        else:
            for i, el in enumerate(it.elements):
                yield from walk(el, f'{p}[{i}]')
