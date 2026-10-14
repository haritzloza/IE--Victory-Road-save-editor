"""Small persistent settings (~/.config/ievr-editor/config.json)."""
import json
import os
from pathlib import Path

PATH = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'ievr-editor' / 'config.json'


def _load():
    try:
        return json.loads(PATH.read_text())
    except (OSError, ValueError):
        return {}


def get(key, default=None):
    return _load().get(key, default)


def set(key, value):
    data = _load()
    data[key] = value
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(data, indent=1))
