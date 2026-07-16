"""把用户项目装进内嵌解释器:uv 主路径 + 内嵌 pip 回退;compileall 预编译。

- uv `--exact` 使 site-packages 与解析结果精确同步(会顺带清掉 pyembed 自带 pip——
  主路径无碍;pip 回退不加 --exact,warn 增量残留风险)。
- `uv pip install` 不读 [tool.uv.sources]:项目对 pyshade 等本地包的依赖须经
  extra_requirements(--with)显式给 wheel/路径。
- compileall 预编译(canary 教训):运行期生成的 .pyc 不在 NSIS 装载清单内,卸载会残留;
  打包前预编译使 .pyc 进 resources 被卸载器追踪,顺带提速冷启动。
"""

import os
import shutil
import subprocess
from pathlib import Path

from loguru import logger as l


class PyembedInstallError(RuntimeError):
    """依赖安装进内嵌解释器失败。"""


def _utf8_env() -> dict[str, str]:
    """子 Python(内嵌 pip/compileall)管道输出走 locale 编码,中文 Windows(GBK)下
    错误信息会 mojibake(errors='replace' 只防崩不防乱码)——强制 UTF-8 模式。"""
    return {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}


def install_command(
    pyembed_python: Path,
    project_dir: Path,
    *,
    dist_name: str,
    extra_requirements: tuple[str, ...] = (),
    uv_path: str | None,
) -> list[str]:
    """组装安装命令(纯函数,单测锚定)。"""
    if uv_path is not None:
        return [
            uv_path,
            'pip',
            'install',
            '--exact',
            # 不读项目 [tool.uv.sources]:dev 态 path 源与 --with 的 wheel 会 URL 冲突(CI 实测)
            '--no-sources',
            f'--python={pyembed_python}',
            f'--reinstall-package={dist_name}',
            str(project_dir),
            *extra_requirements,
        ]
    return [
        str(pyembed_python),
        '-m',
        'pip',
        'install',
        '--upgrade',
        str(project_dir),
        *extra_requirements,
    ]


def install_project(
    pyembed_python: Path,
    project_dir: Path,
    *,
    dist_name: str,
    extra_requirements: tuple[str, ...] = (),
) -> None:
    uv_path = shutil.which('uv')
    if uv_path is None:
        l.warning("pyshade.packager: 未找到 uv,回退内嵌 pip(无 --exact,可能有增量残留;建议安装 uv)")
    command = install_command(
        pyembed_python, project_dir, dist_name=dist_name, extra_requirements=extra_requirements, uv_path=uv_path
    )
    l.info("pyshade.packager: 安装项目进内嵌解释器({} 模式)", 'uv' if uv_path else 'pip')
    result = subprocess.run(
        command, capture_output=True, encoding='utf-8', errors='replace', timeout=1800, env=_utf8_env()
    )
    if result.returncode != 0:
        raise PyembedInstallError(
            f"依赖安装失败(exit {result.returncode}):\n{(result.stderr or result.stdout or '').strip()[-4000:]}\n"
            "本地未发布的依赖(如 path 源的 pyshade)请经 --with 传 wheel 或目录"
        )


def warn_if_wheel_polluted(pyembed_python: Path) -> bool:
    """pytauri-wheel 混进 pyembed 即 warn(standalone 不加载它,纯 +30MB 冗余)。"""
    site_packages = _site_packages(pyembed_python)
    polluted = site_packages is not None and (site_packages / 'pytauri_wheel').is_dir()
    if polluted:
        l.warning(
            "pyshade.packager: 内嵌解释器里发现 pytauri_wheel(约 +30MB,standalone 不会加载它);"
            "请把 pytauri-wheel 从项目 dependencies 挪到 dev 依赖组"
        )
    return polluted


def _site_packages(pyembed_python: Path) -> Path | None:
    python_root = pyembed_python.parent if pyembed_python.parent.name != 'bin' else pyembed_python.parent.parent
    windows_layout = python_root / 'Lib' / 'site-packages'
    if windows_layout.is_dir():
        return windows_layout
    unix = sorted((python_root / 'lib').glob('python3.*/site-packages')) if (python_root / 'lib').is_dir() else []
    return unix[0] if unix else None


def compile_bytecode(pyembed_python: Path) -> None:
    """预编译整个内嵌环境的 .pyc;个别文件编译失败仅 warn(如 stripped 布局缺模板)。"""
    python_root = pyembed_python.parent if pyembed_python.parent.name != 'bin' else pyembed_python.parent.parent
    result = subprocess.run(
        [str(pyembed_python), '-m', 'compileall', '-q', str(python_root)],
        capture_output=True,
        encoding='utf-8',
        errors='replace',
        timeout=1800,
        env=_utf8_env(),
    )
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or '').strip()[-1000:]
        l.warning("pyshade.packager: compileall 有文件未编译(不阻塞打包):{}", tail)
