"""Per-platform folders for settings, cache and backups."""
import os
import sys
from pathlib import Path

APP = 'ievr-editor'


def _env_dir(var, default):
    v = os.environ.get(var)
    return Path(v) if v else default


def config_dir() -> Path:
    if sys.platform == 'win32':
        return _env_dir('APPDATA', Path.home() / 'AppData/Roaming') / APP
    return _env_dir('XDG_CONFIG_HOME', Path.home() / '.config') / APP


def cache_dir() -> Path:
    if sys.platform == 'win32':
        return _env_dir('LOCALAPPDATA', Path.home() / 'AppData/Local') / APP / 'cache'
    return _env_dir('XDG_CACHE_HOME', Path.home() / '.cache') / APP


def data_dir() -> Path:
    """Where save backups are kept (outside the Steam Cloud folder)."""
    if sys.platform == 'win32':
        return _env_dir('LOCALAPPDATA', Path.home() / 'AppData/Local') / APP
    return _env_dir('XDG_DATA_HOME', Path.home() / '.local/share') / APP


def backup_dir() -> Path:
    return data_dir() / 'backups'
