"""Steam / save / game detection against a fake home directory."""
from pathlib import Path

import pytest

from ievr_editor import config, gamedata, savefile, steam


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / '.config'))
    monkeypatch.delenv('IEVR_GAME_DIR', raising=False)
    monkeypatch.setattr(config, 'PATH', tmp_path / '.config/ievr-editor/config.json')
    monkeypatch.setattr(steam, '_windows_roots', lambda: [])  # ignore a real Steam on Windows runners
    return tmp_path


def add_save(root: Path, account: int):
    d = root / 'userdata' / str(account) / str(savefile.APP_ID) / 'remote'
    d.mkdir(parents=True)
    (d / savefile.USERDATA_NAME).write_bytes(b'x')
    return d


def add_game(library: Path):
    d = library / 'steamapps/common' / gamedata.GAME_DIR_NAME / 'data'
    d.mkdir(parents=True)
    (d / 'cpk_list.cfg.bin').write_bytes(b'x')
    return d.parent


def test_no_steam(home):
    assert savefile.find_save_dirs() == []
    assert gamedata.find_game_dir() is None


@pytest.mark.parametrize('root', ['.local/share/Steam', '.var/app/com.valvesoftware.Steam/.local/share/Steam',
                                  'snap/steam/common/.local/share/Steam'])
def test_saves_in_every_steam_flavour(home, root):
    d = add_save(home / root, 42)
    assert savefile.find_save_dirs() == [d.resolve()]


def test_multiple_accounts_with_names(home):
    root = home / '.local/share/Steam'
    add_save(root, 111)
    add_save(root, 222)
    (root / 'config').mkdir()
    (root / 'config/loginusers.vdf').write_text(
        '"users"\n{\n\t"%d"\n\t{\n\t\t"AccountName"\t"x"\n\t\t"PersonaName"\t"Uno"\n\t}\n}\n'
        % (steam.STEAMID64_BASE + 111))
    dirs = savefile.find_save_dirs()
    assert len(dirs) == 2
    labels = [savefile.describe_save_dir(d) for d in dirs]
    assert labels[0].startswith('Uno (111)')
    assert labels[1].startswith('Cuenta (222)')


def test_game_in_secondary_library(home, tmp_path):
    root = home / '.local/share/Steam'
    (root / 'steamapps').mkdir(parents=True)
    lib = tmp_path / 'otro disco' / 'SteamLibrary'
    game = add_game(lib)
    (root / 'steamapps/libraryfolders.vdf').write_text(
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n\t"1"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n'
        % (root, lib))
    assert gamedata.find_game_dir() == game


def test_game_dir_from_config(home, tmp_path):
    game = add_game(tmp_path / 'manual')
    config.set('game_dir', str(game))
    assert gamedata.find_game_dir() == game
    config.set('game_dir', str(tmp_path / 'nope'))
    assert gamedata.find_game_dir() is None
