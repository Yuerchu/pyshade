"""python -m component_gallery:启动 pytauri 桌面应用(standalone/开发双形态见 pyshade.shell)。"""

import sys
from pathlib import Path

from component_gallery.app import app
from pyshade.shell import run

REPO_ROOT = Path(__file__).parents[4]

if __name__ == '__main__':
    sys.exit(run(app, config_dir=Path(__file__).parent, dist_dir=REPO_ROOT / 'frontend' / 'dist'))
