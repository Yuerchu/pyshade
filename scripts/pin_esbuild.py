"""发版工具:拉取全平台 esbuild tarball,生成 _esbuild.py 的 sha256 pin 表。

用法:uv run python scripts/pin_esbuild.py [版本,默认取 _esbuild.ESBUILD_VERSION]
输出可直接粘贴替换 _BINARY_SHA256 的 dict 字面量。
"""

import hashlib
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pyshade.bundler._esbuild import _BINARY_SHA256, DEFAULT_REGISTRY, ESBUILD_VERSION, _binary_member  # noqa: E402


def sha_for(plat: str, version: str) -> str:
    url = f'{DEFAULT_REGISTRY}/@esbuild/{plat}/-/{plat}-{version}.tgz'
    with urllib.request.urlopen(url, timeout=120) as response:
        blob = response.read()
    with tempfile.TemporaryDirectory() as tmp:
        tar_path = Path(tmp) / 'pkg.tgz'
        tar_path.write_bytes(blob)
        with tarfile.open(tar_path, 'r:gz') as tar:
            member = tar.extractfile(_binary_member(plat))
            assert member is not None
            return hashlib.sha256(member.read()).hexdigest()


def main() -> None:
    version = sys.argv[1] if len(sys.argv) > 1 else ESBUILD_VERSION
    print(f"ESBUILD_VERSION = '{version}'")
    print('_BINARY_SHA256: dict[str, str] = {')
    for plat in _BINARY_SHA256:
        sha = sha_for(plat, version)
        print(f"    '{plat}': '{sha}',")
    print('}')


if __name__ == '__main__':
    main()
