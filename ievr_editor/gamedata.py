"""Access to the game's own data tables (names of items, characters, ...).

Everything is read from the user's installed copy of the game; nothing from
the game is bundled with the editor. Extracted files are cached under
``~/.cache/ievr-editor/<game build>/``.
"""
import os
import re
import struct
import zlib
from pathlib import Path

from . import config, cpk, rdbn, steam, t2b
from .paths import cache_dir

GAME_DIR_NAME = 'INAZUMA ELEVEN Victory Road'

# AES-256-CBC key/iv of cpk_list.cfg.bin, stored obfuscated in nie.exe
# (FUN_141740ee0) and revealed with the same keystream as the saves.
_CPK_LIST_KEY = (0x8A90ABA9, (0x72c9cb21, 0x178bf2f9, 0x6450e29d, 0x4da98cd1,
                              0x1e908d53, 0x750df696, 0x43d9a87a, 0x584fe242))
_CPK_LIST_IV = (0x4C801618, (0x3f8e4b6d, 0xf0c9492f, 0x3844e69d, 0xb0cb1ee3))


def _reveal(seed_words):
    from . import crypto
    seed, words = seed_words
    return crypto.xor(b''.join(struct.pack('<I', w) for w in words), seed)


def is_game_dir(d) -> bool:
    return d is not None and (Path(d) / 'data/cpk_list.cfg.bin').is_file()


def find_game_dir():
    """Game install dir: $IEVR_GAME_DIR, the folder saved in the config, or Steam libraries."""
    for d in (os.environ.get('IEVR_GAME_DIR'), config.get('game_dir')):
        if d and is_game_dir(d):
            return Path(d)
    for lib in steam.library_dirs():
        d = lib / 'steamapps/common' / GAME_DIR_NAME
        if is_game_dir(d):
            return d
    return None


def _version_key(name):
    return tuple(int(x) for x in re.findall(r'\d+', name))


class GameData:
    def __init__(self, game_dir=None):
        self.game_dir = Path(game_dir) if game_dir else find_game_dir()
        if not is_game_dir(self.game_dir):
            raise FileNotFoundError('INAZUMA ELEVEN Victory Road install not found')
        raw = (self.game_dir / 'data/cpk_list.cfg.bin').read_bytes()
        build = f'{zlib.crc32(raw):08x}'
        self.cache = cache_dir() / build
        self.index = self._load_index(raw)
        self._cpks = {}

    def _load_index(self, raw):
        from Crypto.Cipher import AES
        plain = AES.new(_reveal(_CPK_LIST_KEY), AES.MODE_CBC, _reveal(_CPK_LIST_IV)).decrypt(
            raw[:len(raw) // 16 * 16])
        plain = plain[:len(plain) - plain[-1]]
        index = {}
        for e in t2b.parse(plain):
            v = e.values
            if len(v) >= 5 and all(isinstance(x, str) for x in v[:4]):
                index[v[0] + v[1]] = v[2] + v[3]
        return index

    def find(self, directory, stem):
        """Path of the newest versioned file ``directory/stem*.cfg.bin``."""
        cands = [p for p in self.index
                 if p.startswith(directory) and p[len(directory):].startswith(stem)
                 and '/' not in p[len(directory):]]
        if not cands:
            raise FileNotFoundError(directory + stem)
        return max(cands, key=lambda p: _version_key(p[len(directory) + len(stem):]))

    def read(self, path) -> bytes:
        cached = self.cache / path
        if cached.exists():
            return cached.read_bytes()
        pack = self.index[path]
        if pack not in self._cpks:
            self._cpks[pack] = cpk.Cpk(self.game_dir / pack)
        data = self._cpks[pack].read(path)
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
        return data

    def table(self, directory, stem):
        """T2B entries (list) or, for RDBN files, {list_name: [records]}."""
        data = self.read(self.find(directory, stem))
        if rdbn.is_rdbn(data):
            return rdbn.parse(data)
        return t2b.parse(data)

    def languages(self):
        return sorted({p.split('/')[3] for p in self.index
                       if p.startswith('data/common/text/') and p.endswith('/item_text.cfg.bin')})

    def texts(self, name, lang='es'):
        """id -> text for NOUN_INFO (variant 0) and TEXT_INFO entries of a text table."""
        out = {}
        path = f'data/common/text/{lang}/{name}.cfg.bin'
        if path not in self.index:
            path = f'data/common/text/en/{name}.cfg.bin'
        for e in t2b.parse(self.read(path)):
            if e.name == 'NOUN_INFO' and e.raw[1] == 0:
                txt = next((x for x in e.values[2:10] if isinstance(x, str) and x), None)
                if txt:
                    out.setdefault(e.raw[0] & 0xFFFFFFFF, txt)
            elif e.name == 'TEXT_INFO' and e.raw[1] == 0 and isinstance(e.values[2], str):
                out.setdefault(e.raw[0] & 0xFFFFFFFF, e.values[2])
        return out
