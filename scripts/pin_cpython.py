"""重新 pin 便携 CPython:拉取 PBS release 的 SHA256SUMS,输出可粘贴的 sha256 表。

用法:uv run python scripts/pin_cpython.py [cpython版本] [release标签]
缺省参数打印当前 pin 的复核结果;升级时给新版本号 + release 标签,
把输出粘进 src/pyshade/packager/_cpython.py 的 _TARBALL_SHA256 与版本常量。
"""

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pyshade.packager._cpython import (  # noqa: E402
    _TRIPLE_MAP,
    CPYTHON_VERSION,
    DEFAULT_BASE,
    PBS_RELEASE,
    tarball_name,
)


def main() -> int:
    version = sys.argv[1] if len(sys.argv) > 1 else CPYTHON_VERSION
    release = sys.argv[2] if len(sys.argv) > 2 else PBS_RELEASE
    url = f'{DEFAULT_BASE}/{release}/SHA256SUMS'
    print(f"# 拉取 {url}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=120) as response:
        sums = response.read().decode('utf-8')

    by_name: dict[str, str] = {}
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2:
            by_name[parts[1]] = parts[0]

    print(f"CPYTHON_VERSION = '{version}'")
    print(f"PBS_RELEASE = '{release}'")
    print()
    print('_TARBALL_SHA256: dict[str, str] = {')
    missing: list[str] = []
    for triple in dict.fromkeys(_TRIPLE_MAP.values()):
        name = tarball_name(triple, version=version, release=release)
        digest = by_name.get(name)
        if digest is None:
            missing.append(name)
            continue
        print(f"    '{triple}': '{digest}',")
    print('}')
    if missing:
        print(f"# 缺失 asset:{missing}", file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
