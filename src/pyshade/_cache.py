"""用户级缓存目录(bundler 的 esbuild 与 packager 的便携 CPython 共用)。"""

import os
import platform
from pathlib import Path


def cache_root() -> Path:
    override = os.environ.get('PYSHADE_CACHE_DIR')
    if override:
        return Path(override)
    system = platform.system().lower()
    if system == 'windows':
        base = os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))
        return Path(base) / 'pyshade'
    if system == 'darwin':
        return Path.home() / 'Library' / 'Caches' / 'pyshade'
    xdg = os.environ.get('XDG_CACHE_HOME')
    return (Path(xdg) if xdg else Path.home() / '.cache') / 'pyshade'
