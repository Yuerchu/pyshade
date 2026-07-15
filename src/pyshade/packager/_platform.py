"""平台修补与构建环境(纯函数为主,单测锚定)。

- Windows:无需处理(pytauri 官方文档 "Nothing you need to do")。
- macOS:PBS 的 libpython dylib 缺 @rpath install_name,需 install_name_tool 修补;
  RUSTFLAGS 指 rpath 到 .app 的 Resources/lib。
- Linux:RUSTFLAGS 指 rpath 到 $ORIGIN/../lib/<productName>/lib(deb 布局),
  另加一条 $ORIGIN/../lib 对冲 AppImage 的 libpython 挪位问题(tauri#11898)。
"""

import subprocess
from pathlib import Path

from loguru import logger as l


class PlatformPatchError(RuntimeError):
    """平台修补失败(如 macOS 缺 install_name_tool)。"""


def rustflags_for(system: str, *, product_name: str, pyembed_lib: Path) -> str | None:
    """按平台组装 RUSTFLAGS;Windows 返回 None(不设)。"""
    if system == 'windows':
        return None
    if system == 'darwin':
        return f'-C link-arg=-Wl,-rpath,@executable_path/../Resources/lib -L {pyembed_lib}'
    return (
        f'-C link-arg=-Wl,-rpath,$ORIGIN/../lib/{product_name}/lib '
        f'-C link-arg=-Wl,-rpath,$ORIGIN/../lib '
        f'-L {pyembed_lib}'
    )


def build_env(
    base_env: dict[str, str],
    *,
    system: str,
    pyembed_python: Path,
    pyembed_dir: Path,
    product_name: str,
) -> dict[str, str]:
    """cargo-tauri build 的 subprocess env:PYO3_PYTHON + 平台 RUSTFLAGS(追加不覆盖)。"""
    env = dict(base_env)
    env['PYO3_PYTHON'] = str(pyembed_python)
    flags = rustflags_for(system, product_name=product_name, pyembed_lib=pyembed_dir / 'python' / 'lib')
    if flags is not None:
        existing = env.get('RUSTFLAGS', '').strip()
        env['RUSTFLAGS'] = f'{existing} {flags}'.strip()
    return env


def patch_macos_dylib(pyembed_dir: Path) -> list[Path]:
    """macOS:对 pyembed 内每个 libpython3.*.dylib 跑 install_name_tool(幂等);返回修补清单。"""
    lib_dir = pyembed_dir / 'python' / 'lib'
    dylibs = sorted(lib_dir.glob('libpython3.*.dylib'))
    if not dylibs:
        raise PlatformPatchError(f"{lib_dir} 下未找到 libpython3.*.dylib;PBS 布局异常")
    for dylib in dylibs:
        result = subprocess.run(
            ['install_name_tool', '-id', f'@rpath/{dylib.name}', str(dylib)],
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            timeout=120,
        )
        if result.returncode != 0:
            raise PlatformPatchError(
                f"install_name_tool 失败(exit {result.returncode}):{result.stderr.strip()[-1000:]};"
                "缺工具请先 xcode-select --install"
            )
        l.debug("pyshade.packager: 已修补 {} 的 install_name", dylib.name)
    return dylibs
