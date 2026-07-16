"""发版 wheel 完整性断言(ci.yml 与 release.yml 的 wheel-assets 共用)。

零 Node 管线的资产全走包数据(design.md §3.6),漏一件 = 用户 bundle 直接废——
与 hatch_build 的 PYSHADE_REQUIRE_FRONTEND_ASSETS 严格模式互为双保险。
"""

import glob
import sys
import zipfile

_REQUIRED = (
    'pyshade/_frontend/static/style.css',
    'pyshade/_frontend/static/index.html',
    'pyshade/_frontend/vendor-manifest.json',
    'pyshade/_frontend/src/runtime/page.ts',
    'pyshade/_frontend/src/runtime/scheme.ts',
    'pyshade/_frontend/src/ipc/shadeFetch.ts',
    'pyshade/_frontend/vendor/node_modules/react/package.json',
)


def main() -> int:
    wheels = glob.glob('dist/pyshade-*.whl')
    if not wheels:
        print("dist/ 下没有 pyshade wheel", file=sys.stderr)
        return 1
    wheel = wheels[0]
    names = set(zipfile.ZipFile(wheel).namelist())
    missing = [entry for entry in _REQUIRED if entry not in names]
    if missing:
        print(f"wheel 缺件:{missing}", file=sys.stderr)
        return 1
    print(f'wheel OK: {wheel} ({len(names)} entries)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
