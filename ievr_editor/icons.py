"""Item and character icons extracted from the game into a PNG cache.

Keys:  ``item:<code>``  item code from item_config (icon atlas texture or icon file)
       ``face:<code>``  character model code from chara_base (face icon)
       ``file:<name>``  any icon file under menu/200_icon (e.g. keshin ``k000010_l``)
"""
import io
import threading
from pathlib import Path
from typing import Optional

from PIL import Image

from . import g4tx
from .gamedata import GameData

ICON_ROOT = 'data/dx11/menu/200_icon/'
ATLAS_DIR = ICON_ROOT + '02_icon_item/'
FACE_DIR = ICON_ROOT + '10_icon_chr/face/'
SIZE = 128


class IconStore:
    def __init__(self, gd: GameData):
        self.gd = gd
        self.dir = gd.cache / 'icons'
        self.lock = threading.Lock()
        self.files = {p.rsplit('/', 1)[1][:-5]: p for p in gd.index
                      if p.startswith(ICON_ROOT) and p.endswith('.g4tx')}
        self._atlas = None
        self.missing = set()

    def _atlas_index(self):
        if self._atlas is None:
            self._atlas = {}
            for p in sorted(p for p in self.gd.index if p.startswith(ATLAS_DIR) and p.endswith('.g4tx')):
                for i, (name, _) in enumerate(g4tx.textures(self.gd.read(p))):
                    self._atlas.setdefault(name, (p, i))
        return self._atlas

    def _source(self, key):
        """(g4tx path, texture index) for a key, or None."""
        kind, _, name = key.partition(':')
        if kind == 'face':
            p = self.files.get(f'{name}_l')
            return (p, 0) if p and p.startswith(FACE_DIR) else None
        if kind == 'file':
            p = self.files.get(name)
            return (p, 0) if p else None
        if kind == 'item':
            if name in self._atlas_index():
                return self._atlas[name]
            for n in (f'{name}_l', name, name.split('_', 1)[-1] + '_l'):
                if n in self.files:
                    return self.files[n], 0
        return None

    def png(self, key: str) -> Optional[Path]:
        """Path of the cached PNG for a key (extracted on first use), or None."""
        out = self.dir / (key.replace(':', '_').replace('/', '_') + '.png')
        if out.exists():
            return out
        if key in self.missing:
            return None
        with self.lock:
            if out.exists():
                return out
            try:
                src = self._source(key)
                if not src:
                    self.missing.add(key)
                    return None
                path, idx = src
                _, dds = g4tx.textures(self.gd.read(path))[idx]
                img = Image.open(io.BytesIO(dds))
                img.load()
                img = img.convert('RGBA')
                bbox = img.getbbox()  # trim transparent borders so small icons fill the cell
                if bbox:
                    img = img.crop(bbox)
                img.thumbnail((SIZE, SIZE), Image.LANCZOS)
                out.parent.mkdir(parents=True, exist_ok=True)
                img.save(out)
                return out
            except Exception:
                self.missing.add(key)
                return None
