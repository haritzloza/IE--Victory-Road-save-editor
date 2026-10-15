"""Open, edit and write back the Steam save of IEVR."""
import glob
import shutil
import time
from pathlib import Path

from . import container, l5bin, paths, steam

APP_ID = 2799860
USERDATA_NAME = '002AB8F4-USERDATALIVE'
MAX_BACKUPS = 20
# newest game / save-format versions the editor has been checked against
TESTED_APP_VERSION = (7, 1)
TESTED_FORMAT_VERSION = 90
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

    def versions(self):
        """(game version (major, minor), save format version) recorded in the save."""
        p = l5bin.find(self.section(1).items, 'm_Permanent').items
        g = lambda n: int.from_bytes(l5bin.find(p, n).data, 'little')
        return (g('release_app_version'), g('minor_app_version')), g('minor_version')

    def newer_than_tested(self) -> bool:
        app, fmt = self.versions()
        return app > TESTED_APP_VERSION or fmt > TESTED_FORMAT_VERSION

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
        """Write the save; the previous file is copied to the backups folder first."""
        target = Path(path) if path else self.path
        data = self.to_bytes()
        container.Container.load(data)  # sanity check before touching the disk
        write_with_backup(target, data, backup_dir)


def make_backup(target: Path, backup_dir=None):
    """Copy ``target`` to the backups folder (outside Steam Cloud), keeping the newest MAX_BACKUPS."""
    if not target.exists():
        return
    bdir = Path(backup_dir) if backup_dir else paths.backup_dir()
    bdir.mkdir(parents=True, exist_ok=True)
    dest = bdir / f'{target.name}.{time.strftime("%Y%m%d-%H%M%S")}'
    n = 1
    while dest.exists():  # two backups within the same second
        dest = dest.with_name(f'{dest.name.split("-v")[0]}-v{n}')
        n += 1
    shutil.copy2(target, dest)
    for old in sorted(bdir.glob(f'{target.name}.*'))[:-MAX_BACKUPS]:
        old.unlink()


def write_with_backup(target: Path, data: bytes, backup_dir=None):
    make_backup(target, backup_dir)
    tmp = target.with_suffix('.tmp')
    tmp.write_bytes(data)
    tmp.replace(target)


def list_backups(name=USERDATA_NAME, backup_dir=None):
    """[(path, datetime text, size)] newest first."""
    bdir = Path(backup_dir) if backup_dir else paths.backup_dir()
    out = []
    for p in sorted(bdir.glob(f'{name}.*'), reverse=True):
        stamp = p.name[len(name) + 1:][:15]
        try:
            when = time.strftime('%d/%m/%Y %H:%M:%S', time.strptime(stamp, '%Y%m%d-%H%M%S'))
        except ValueError:
            continue
        out.append((p, when, p.stat().st_size))
    return out


def restore_backup(backup: Path, target: Path, backup_dir=None):
    """Put a backup back in place (the current save is backed up first)."""
    data = Path(backup).read_bytes()  # read before rotating: it may be the oldest backup
    container.Container.load(data)     # refuse anything that isn't a valid save
    write_with_backup(Path(target), data, backup_dir)
