"""cargo / cargo-tauri 探测与 tauri build 调用。

前置体检一次性汇总全部缺项(不挤牙膏);build 不捕获输出(编译长达数分钟,
进度直通终端),失败时附常见错误的静态提示。
"""

import shutil
import subprocess
from pathlib import Path

from loguru import logger as l


class TauriCliError(RuntimeError):
    """前置工具缺失或 tauri build 失败。"""


def preflight_issues(project_dir: Path) -> list[str]:
    """汇总打包前置缺项;空列表 = 就绪。"""
    issues: list[str] = []
    if not (project_dir / 'src-tauri' / 'tauri.conf.json').is_file():
        issues.append(f"{project_dir} 下没有 src-tauri/ 打包工程 → 先运行 pyshade init --dir {project_dir}")
    if shutil.which('cargo') is None:
        issues.append(
            "缺少 Rust 工具链(cargo)→ 安装 rustup:https://rustup.rs"
            "(Windows 另需 Visual Studio Build Tools 的 MSVC 组件)"
        )
    tauri_cli = shutil.which('cargo-tauri')
    if tauri_cli is None:
        issues.append("缺少 tauri-cli → cargo install tauri-cli --version '^2' --locked")
    else:
        result = subprocess.run(
            [tauri_cli, '--version'], capture_output=True, encoding='utf-8', errors='replace', timeout=60
        )
        version = (result.stdout or '').strip()
        if 'tauri-cli 2' not in version:
            issues.append(
                f"tauri-cli 版本不符(需要 2.x,当前 {version or '未知'})→ cargo install tauri-cli --version '^2'"
            )
    return issues


def tauri_build_command(*, bundles: tuple[str, ...], profile: str) -> list[str]:
    """组装 cargo-tauri build 命令(纯函数,单测锚定)。"""
    return [
        'cargo-tauri',
        'build',
        '--config',
        'src-tauri/tauri.bundle.json',
        '--bundles',
        ','.join(bundles),
        '--',
        '--profile',
        profile,
    ]


_FAILURE_HINTS = (
    "常见原因:\n"
    "  - `cannot find -lpython3.x` → RUSTFLAGS/-L 未生效或 pyembed 缺失(重跑并勿手动改 env)\n"
    "  - `webkit2gtk`/`javascriptcore` 缺失(Linux)→ apt install libwebkit2gtk-4.1-dev "
    "build-essential libssl-dev libayatana-appindicator3-dev librsvg2-dev\n"
    "  - `link.exe not found`(Windows)→ 安装 Visual Studio Build Tools 的 MSVC 组件\n"
    "  - macOS 运行期找不到 libpython → install_name_tool 修补步骤被跳过(勿用 --skip 类手段绕过)"
)


def run_tauri_build(
    project_dir: Path,
    env: dict[str, str],
    *,
    bundles: tuple[str, ...],
    profile: str,
) -> None:
    """执行 tauri build;输出直通终端(不捕获),失败附静态提示。"""
    command = tauri_build_command(bundles=bundles, profile=profile)
    l.info("pyshade.packager: {}(PYO3_PYTHON={})", ' '.join(command), env.get('PYO3_PYTHON', ''))
    result = subprocess.run(command, cwd=project_dir, env=env, timeout=3600)
    if result.returncode != 0:
        raise TauriCliError(f"tauri build 失败(exit {result.returncode});输出见上方。\n{_FAILURE_HINTS}")
