"""Check GitHub for a newer release (only the public releases API is contacted)."""
import json
import re
import ssl
import urllib.request

from . import REPO, __version__


def _version(tag: str):
    return tuple(int(x) for x in re.findall(r'\d+', tag)[:3])


def latest_release(timeout=6):
    """(tag, page url) of the newest release if it is newer than this build, else None."""
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    req = urllib.request.Request(f'https://api.github.com/repos/{REPO}/releases/latest',
                                 headers={'Accept': 'application/vnd.github+json',
                                          'User-Agent': f'ievr-save-editor/{__version__}'})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        data = json.load(r)
    tag = data.get('tag_name', '')
    if tag and _version(tag) > _version(__version__):
        return tag, data.get('html_url') or f'https://github.com/{REPO}/releases/latest'
    return None
