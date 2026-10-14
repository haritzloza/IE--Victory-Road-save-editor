"""Level-5 RDBN tables (typed ``.cfg.bin`` files such as skill_config).

Each root list has a record type; each type has named fields with an element
type, size, count and offset inside the record.
"""
import struct

_FMT = {3: '?', 4: 'B', 5: 'h', 9: 'h', 6: 'i', 10: 'i', 0xD: 'f', 0xF: 'I'}


def is_rdbn(data: bytes) -> bool:
    return data[:4] == b'RDBN'


def parse(data: bytes) -> dict:
    """Return {list_name: [record dict, ...]}. Multi-value fields become lists."""
    (magic, _hsize, _ver, data_off, _dsize) = struct.unpack_from('<4shihi', data, 0)
    if magic != b'RDBN':
        raise ValueError('not RDBN')
    (type_off, type_cnt, field_off, field_cnt, root_off, root_cnt, hash_off, offs_off,
     hash_cnt, value_off, string_off) = struct.unpack_from('<10hi', data, 0x24)
    base = data_off << 2
    string_off += base

    def cstr(o):
        return data[o:data.index(b'\0', o)].decode('utf-8', 'replace')

    hp, op = (hash_off << 2) + base, (offs_off << 2) + base
    names = {struct.unpack_from('<I', data, hp + 4 * i)[0]:
             cstr(string_off + struct.unpack_from('<i', data, op + 4 * i)[0]) for i in range(hash_cnt)}

    fields = []
    p = (field_off << 2) + base
    for i in range(field_cnt):
        h, typ, _cat, size, voff, vcnt = struct.unpack_from('<Ihhiii', data, p + 0x20 * i)
        fields.append((names.get(h, f'#{h:08x}'), typ, size, voff, vcnt))
    types = []
    p = (type_off << 2) + base
    for i in range(type_cnt):
        h, _unk, fidx, fcnt = struct.unpack_from('<IIhh', data, p + 0x20 * i)
        types.append(fields[fidx:fidx + fcnt])

    values_base = (value_off << 2) + base
    out = {}
    p = (root_off << 2) + base
    for i in range(root_cnt):
        tidx, _u, voff, vsize, vcnt, h = struct.unpack_from('<hhiiiI', data, p + 0x20 * i)
        recs = []
        for j in range(vcnt):
            rec_off = values_base + voff + j * vsize
            rec = {}
            for fname, typ, size, foff, fcnt in types[tidx]:
                vals = []
                q = rec_off + foff
                for _ in range(fcnt):
                    if typ in _FMT:
                        vals.append(struct.unpack_from('<' + _FMT[typ], data, q)[0])
                    elif typ == 0x14:
                        o = struct.unpack_from('<I', data, q)[0]
                        vals.append(cstr(string_off + o) if string_off + o < len(data) else o)
                    elif typ in (0x12, 0x13):
                        vals.append(struct.unpack_from('<4f', data, q))
                    elif typ == 0x15:
                        vals.append(struct.unpack_from('<2h', data, q))
                    else:
                        vals.append(data[q:q + size])
                    q += size
                rec[fname] = vals[0] if fcnt == 1 else vals
            recs.append(rec)
        out[names.get(h, f'#{h:08x}')] = recs
    return out
