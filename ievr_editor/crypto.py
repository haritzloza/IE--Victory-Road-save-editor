"""Keystream used by IEVR to obfuscate save containers (and embedded keys).

Reimplementation of nie.exe FUN_1404d4aa0. For every 4-byte aligned position
``p`` the game computes ``crc = zlib.crc32(seed_le32, p)`` and spreads its 32
bits over the next four key bytes (2 bits from each crc byte per key byte).
"""
import struct
import zlib

import numpy as np


def _key_bytes(crc: int) -> bytes:
    out = bytearray(4)
    for s in range(4):
        r = 2 * s
        out[s] = (((crc >> r) & 3) << 6 | ((crc >> (r + 8)) & 3) << 4
                  | ((crc >> (r + 16)) & 3) << 2 | ((crc >> (r + 24)) & 3))
    return bytes(out)


def keystream(seed: int, length: int, offset: int = 0) -> np.ndarray:
    """Keystream bytes for stream positions [offset, offset + length)."""
    sb = struct.pack('<I', seed)
    start = offset & ~3
    n = (offset + length - start + 3) // 4
    # crc32(sb, p) is affine in p over GF(2): crc(p) = L(p) ^ crc(0), so build it
    # from the per-bit contributions instead of calling zlib n times.
    base = zlib.crc32(sb, 0)
    pos = (np.arange(n, dtype=np.uint64) * 4 + start).astype(np.uint32)
    crc = np.full(n, base, dtype=np.uint32)
    for bit in range(32):
        contrib = zlib.crc32(sb, 1 << bit) ^ base
        if contrib:
            crc ^= np.where((pos >> np.uint32(bit)) & 1, np.uint32(contrib), np.uint32(0))
    ks = np.zeros((n, 4), dtype=np.uint8)
    for s in range(4):
        r = 2 * s
        ks[:, s] = (((crc >> r) & 3) << 6 | ((crc >> (r + 8)) & 3) << 4
                    | ((crc >> (r + 16)) & 3) << 2 | ((crc >> (r + 24)) & 3)).astype(np.uint8)
    skip = offset - start
    return ks.reshape(-1)[skip:skip + length]


def xor(data: bytes, seed: int, offset: int = 0) -> bytes:
    a = np.frombuffer(data, dtype=np.uint8)
    return (a ^ keystream(seed, len(a), offset)).tobytes()


def _crc_from_key4(k4: bytes) -> int:
    crc = 0
    for s, k in enumerate(k4):
        r = 2 * s
        crc |= (((k >> 6) & 3) << r | ((k >> 4) & 3) << (r + 8)
                | ((k >> 2) & 3) << (r + 16) | (k & 3) << (r + 24))
    return crc


def _seed_for_crc(target: int, pos: int = 0) -> int:
    """Solve zlib.crc32(seed_le32, pos) == target for seed (linear over GF(2))."""
    base = zlib.crc32(b'\0\0\0\0', pos)
    pivots = {}
    for i in range(32):
        v, m = zlib.crc32(struct.pack('<I', 1 << i), pos) ^ base, 1 << i
        for b in sorted(pivots, reverse=True):
            if v >> b & 1:
                v ^= pivots[b][0]
                m ^= pivots[b][1]
        if v:
            pivots[v.bit_length() - 1] = (v, m)
    v, m = target ^ base, 0
    for b in sorted(pivots, reverse=True):
        if v >> b & 1:
            v ^= pivots[b][0]
            m ^= pivots[b][1]
    if v:
        raise ValueError('no seed produces this crc')
    return m


def recover_seed(cipher: bytes, known_plain_u32: int) -> int:
    """Recover the seed from the first 4 bytes of a buffer whose plaintext is known."""
    k4 = bytes(a ^ b for a, b in zip(cipher[:4], struct.pack('<I', known_plain_u32)))
    seed = _seed_for_crc(_crc_from_key4(k4))
    assert _key_bytes(zlib.crc32(struct.pack('<I', seed), 0)) == k4
    return seed
