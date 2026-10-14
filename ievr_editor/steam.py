"""Locating Steam, its libraries and its user accounts (Linux and Windows)."""
import os
import re
import sys
from pathlib import Path

STEAMID64_BASE = 76561197960265728


def _windows_roots():
    """Steam dir from the registry, plus the default install locations."""
    if sys.platform != 'win32':
        return []
    out = []
    try:
        import winreg
        for hive, key, value in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                                 (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath')):
            try:
                with winreg.OpenKey(hive, key) as k:
                    out.append(Path(winreg.QueryValueEx(k, value)[0]))
            except OSError:
                pass
    except ImportError:
        pass
    for env in ('ProgramFiles(x86)', 'ProgramFiles'):
        if os.environ.get(env):
            out.append(Path(os.environ[env]) / 'Steam')
    return out


def steam_roots():
    """Existing Steam install dirs (Linux native/Flatpak/Snap/Steam Deck, Windows)."""
    home = Path.home()
    cands = [home / '.local/share/Steam', home / '.steam/steam', home / '.steam/root',
             home / '.var/app/com.valvesoftware.Steam/.local/share/Steam',
             home / '.var/app/com.valvesoftware.Steam/data/Steam',
             home / 'snap/steam/common/.local/share/Steam'] + _windows_roots()
    out = []
    for c in cands:
        if c.is_dir():
            r = c.resolve()
            if r not in out:
                out.append(r)
    return out


def library_dirs():
    """Steam library folders from every root's libraryfolders.vdf."""
    out = []
    for root in steam_roots():
        for vdf in (root / 'steamapps/libraryfolders.vdf', root / 'config/libraryfolders.vdf'):
            if vdf.exists():
                for p in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(errors='replace')):
                    p = Path(p.replace('\\\\', '/'))
                    if p not in out:
                        out.append(p)
        if root not in out:
            out.append(root)
    return out


def account_names():
    """Steam account id (userdata folder name) -> persona name."""
    names = {}
    for root in steam_roots():
        vdf = root / 'config/loginusers.vdf'
        if not vdf.exists():
            continue
        text = vdf.read_text(errors='replace')
        for sid, body in re.findall(r'"(7656\d{13})"\s*\{(.*?)\}', text, re.S):
            m = re.search(r'"PersonaName"\s+"([^"]*)"', body)
            if m:
                names[int(sid) - STEAMID64_BASE] = m.group(1)
    return names
