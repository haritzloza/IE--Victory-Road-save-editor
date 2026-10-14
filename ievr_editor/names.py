"""Field names for the crc32 hashes used in the save tree.

``data/field_names.json`` is generated from nie.exe with ``build_from_exe`` and
only keeps hashes that actually occur in saves.
"""
import json
import re
import zlib
from pathlib import Path

_PATH = Path(__file__).parent / 'data' / 'field_names.json'
_names = None


def _load():
    global _names
    if _names is None:
        _names = {}
        if _PATH.exists():
            _names = {int(k, 16): v for k, v in json.loads(_PATH.read_text()).items()}
    return _names


def name_of(h: int) -> str:
    return _load().get(h) or f'#{h:08x}'


def hash_of(name: str) -> int:
    return zlib.crc32(name.encode())


def build_from_exe(exe_path, wanted_hashes) -> dict:
    """Map wanted hashes to identifiers found in the game executable."""
    data = Path(exe_path).read_bytes()
    wanted = set(wanted_hashes)
    found = {}
    for m in re.finditer(rb'[\x20-\x7e]{2,120}', data):
        s = m.group()
        for tok in {s} | set(re.findall(rb'[A-Za-z_][A-Za-z0-9_.]*', s)):
            h = zlib.crc32(tok)
            if h in wanted and h not in found:
                found[h] = tok.decode()
    return found


def save(found: dict):
    _PATH.parent.mkdir(exist_ok=True)
    _PATH.write_text(json.dumps({f'{k:08x}': v for k, v in sorted(found.items())}, indent=0))
    global _names
    _names = None
