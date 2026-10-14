"""Open, edit and write back the Steam save of IEVR."""
import glob
import shutil
import time
from pathlib import Path

from . import container, l5bin, paths, steam

APP_ID = 2799860
USERDATA_NAME = '002AB8F4-USERDATALIVE'
MAX_BACKUPS = 20
SYSTEM_NAME = '002AB8F4-SYSTEMLIVE'


def find_save_dirs():
    """All Steam ``userdata/<account>/2799860/remote`` dirs holding a save."""
    found = []
    for root in steam.steam_roots():
        for d in sorted(glob.glob(str(root / 'userdata/*' / str(APP_ID) / 'remote'))):
            d = Path(d).resolve()
            if (d / USERDATA_NAME).exists() and d not in found:
                found.append(d)
    return found


def describe_save_dir(d: Path) -> str:
    """Human label for a save dir: Steam persona name, account id and last save time."""
    account = d.parent.parent.name
    name = steam.account_names().get(int(account)) if account.isdigit() else None
    when = time.strftime('%d/%m/%Y %H:%M', time.localtime((d / USERDATA_NAME).stat().st_mtime))
    return f'{name or "Cuenta"} ({account}) · guardado {when}'


class SaveFile:
    """The user-data save: AUTOSAVE (game state) + HEADERSAVE (load-screen summary)."""

    def __init__(self, path):
        self.path = Path(path)
        self.container = container.Container.load(self.path.read_bytes())
        self.sections = {}
        self.order = {}
        for e in self.container.entries:
            secs = l5bin.parse(e.data)
            self.order[e.name] = [s.section_id for s in secs]
            self.sections[e.name] = {s.section_id: s for s in secs}

    def section(self, sid, entry='AUTOSAVE_data.bin') -> l5bin.Section:
        return self.sections[entry][sid]

    def get(self, sid, path, entry='AUTOSAVE_data.bin'):
        return l5bin.get(self.section(sid, entry).items, path)

    def to_bytes(self) -> bytes:
        for e in self.container.entries:
            secs = [self.sections[e.name][sid] for sid in self.order[e.name]]
            e.data = l5bin.serialize(secs)
        return self.container.dump()

    def save(self, path=None, backup_dir=None):
        """Write the save; the previous file is copied to ``backup_dir`` first."""
        target = Path(path) if path else self.path
        data = self.to_bytes()
        container.Container.load(data)  # sanity check before touching the disk
        if target.exists():
            # keep backups out of the Steam Cloud folder
            bdir = Path(backup_dir) if backup_dir else paths.backup_dir()
            bdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, bdir / f'{target.name}.{time.strftime("%Y%m%d-%H%M%S")}')
            for old in sorted(bdir.glob(f'{target.name}.*'))[:-MAX_BACKUPS]:
                old.unlink()
        tmp = target.with_suffix('.tmp')
        tmp.write_bytes(data)
        tmp.replace(target)
