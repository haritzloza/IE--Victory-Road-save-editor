"""Small persistent settings (config.json in the platform's config folder)."""
import json

from .paths import config_dir

PATH = config_dir() / 'config.json'


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
