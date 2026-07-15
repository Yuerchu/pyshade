"""`python -m pyshade.dev`:dev worker 入口(supervisor 以子进程拉起)。"""

import sys

from pyshade.dev._worker import main

if __name__ == '__main__':
    sys.exit(main())
