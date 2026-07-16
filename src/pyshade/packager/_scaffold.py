"""pyshade init:生成 src-tauri 打包工程(模板即真相,渲染参数从用户项目推断)。

参数推断链:pkg_name = src/ 下唯一含 __init__.py 的目录;name/version 读 pyproject.toml;
productName/identifier/窗口 读 `src/<pkg>/Tauri.toml`(dev 态配置即真相),缺省降级 + warn。
幂等:已存在的文件跳过(汇总列出),--force 全量覆盖。
"""

import json
import re
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, cast

from loguru import logger as l

from pyshade.packager._render import render

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class ScaffoldError(RuntimeError):
    """init 前置条件不满足(项目布局/参数推断失败)。"""


@dataclass(frozen=True, slots=True)
class InitParams:
    """模板渲染参数(全部标量)。"""

    crate_name: str
    lib_name: str
    pkg_name: str
    product_name: str
    identifier: str
    version: str
    window_title: str
    window_width: int
    window_height: int


@dataclass(frozen=True, slots=True)
class InitResult:
    src_tauri_dir: Path
    created: list[Path]
    skipped: list[Path]


# (模板内相对路径, 生成相对路径, 是否渲染);dotfile 在模板里去点存放(打包器不吞)
_MANIFEST: list[tuple[str, str, bool]] = [
    ('Cargo.toml.tmpl', 'Cargo.toml', True),
    ('build.rs', 'build.rs', False),
    ('src/lib.rs', 'src/lib.rs', False),
    ('src/main.rs.tmpl', 'src/main.rs', True),
    ('tauri.conf.json.tmpl', 'tauri.conf.json', True),
    ('tauri.bundle.json', 'tauri.bundle.json', False),
    ('taurignore', '.taurignore', False),
    ('gitignore', '.gitignore', False),
    ('capabilities/default.toml', 'capabilities/default.toml', False),
    ('icons/icon.png', 'icons/icon.png', False),
    ('icons/icon.ico', 'icons/icon.ico', False),
]


def load_toml(path: Path) -> dict[str, Any]:
    with path.open('rb') as fh:
        return tomllib.load(fh)


def detect_package(project_dir: Path, package: str | None) -> str:
    if package is not None:
        if not (project_dir / 'src' / package / '__init__.py').is_file():
            raise ScaffoldError(f"src/{package}/__init__.py 不存在;--package 需指向 src 布局下的包名")
        return package
    src = project_dir / 'src'
    if not src.is_dir():
        raise ScaffoldError(f"{project_dir} 下没有 src/ 目录;pyshade init 需要 src 布局的项目")
    candidates = sorted(p.name for p in src.iterdir() if p.is_dir() and (p / '__init__.py').is_file())
    if len(candidates) != 1:
        raise ScaffoldError(f"src/ 下找到 {len(candidates)} 个包({candidates});请用 --package 指定")
    return candidates[0]


def read_pyproject(project_dir: Path, *, version_override: str | None = None) -> tuple[str, str]:
    """返回 (发行名, 版本);version 缺失/dynamic 不再静默降级——报错指向 --version。"""
    pyproject = project_dir / 'pyproject.toml'
    if not pyproject.is_file():
        raise ScaffoldError(f"{project_dir} 下没有 pyproject.toml;pyshade init 需要在项目根运行(--dir 指定)")
    data = load_toml(pyproject)
    project = cast('dict[str, Any]', data.get('project', {}))
    name = str(project.get('name', '')) or project_dir.name
    if version_override is not None:
        return name, version_override
    dynamic = cast('list[str]', project.get('dynamic', []))
    if 'version' in dynamic:
        raise ScaffoldError(
            "pyproject.toml 的 version 是 dynamic(构建期才产生)→ pyshade init 无法推断,"
            "请用 --version 显式传入(如 --version 1.2.3)"
        )
    version = str(project.get('version', ''))
    if not version:
        raise ScaffoldError(
            "pyproject.toml 缺少 [project].version → 请补充,或用 --version 显式传入(如 --version 1.2.3)"
        )
    return name, version


def _read_tauri_toml(config_path: Path) -> tuple[str | None, str | None, tuple[str, int, int] | None]:
    """从用户 dev 态 Tauri.toml 取 (productName, identifier, 窗口);缺文件返回全 None。"""
    if not config_path.is_file():
        return None, None, None
    data = load_toml(config_path)
    product_name = cast('str | None', data.get('productName'))
    identifier = cast('str | None', data.get('identifier'))
    window: tuple[str, int, int] | None = None
    app = cast('dict[str, Any]', data.get('app', {}))
    windows = cast('list[dict[str, Any]]', app.get('windows', []))
    if windows:
        first = windows[0]
        window = (
            str(first.get('title', '')),
            int(first.get('width', 800)),
            int(first.get('height', 600)),
        )
    return product_name, identifier, window


_CRATE_NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_-]*$')
_IDENTIFIER_RE = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$')
_SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+$')
_PRODUCT_FORBIDDEN = frozenset('"\\/') | {chr(c) for c in range(0x20)}


def _validate_params(params: InitParams) -> None:
    """渲染前校验(值进入 Cargo.toml/tauri.conf.json/Rust 源码,非法即报错不做转义魔法):
    此前 productName 含引号会静默产出非法 JSON,直到 pyshade package 才由 cargo-tauri 报晦涩错。"""
    if not _CRATE_NAME_RE.fullmatch(params.crate_name):
        raise ScaffoldError(
            f"crate 名 '{params.crate_name}'(由 pyproject [project].name 推得)不是合法 cargo 包名"
            "(需字母开头,仅字母/数字/-/_)→ 请调整发行名"
        )
    if not params.pkg_name.isidentifier():
        raise ScaffoldError(f"包名 '{params.pkg_name}' 不是合法 Python 标识符(进入生成的 Rust 启动源码)")
    if not _IDENTIFIER_RE.fullmatch(params.identifier) or '.' not in params.identifier:
        raise ScaffoldError(
            f"identifier '{params.identifier}' 非法(仅字母/数字/./-,含至少一个点,形如 cn.example.myapp)→ "
            "请用 --identifier 或 Tauri.toml 提供"
        )
    if any(char in _PRODUCT_FORBIDDEN for char in params.product_name):
        raise ScaffoldError(
            f"产品名 '{params.product_name}' 含非法字符(引号/反斜杠/斜杠/控制字符)→ "
            "产品名进入 tauri.conf.json 与安装包文件名,请仅用常规文字(空格允许)"
        )
    if not _SEMVER_RE.fullmatch(params.version):
        raise ScaffoldError(
            f"版本 '{params.version}' 无法转为 semver(cargo/tauri 需要 主.次.修 三段式)→ "
            "请使用三段式版本,或用 --version 传打包版本(如 0.1.0.dev0 → --version 0.1.0)"
        )


def infer_params(
    project_dir: Path,
    *,
    package: str | None = None,
    product_name: str | None = None,
    identifier: str | None = None,
    version: str | None = None,
) -> InitParams:
    pkg_name = detect_package(project_dir, package)
    dist_name, resolved_version = read_pyproject(project_dir, version_override=version)
    crate_name = dist_name.replace('_', '-')
    lib_name = f'{crate_name.replace("-", "_")}_lib'

    toml_product, toml_identifier, toml_window = _read_tauri_toml(project_dir / 'src' / pkg_name / 'Tauri.toml')
    resolved_product = product_name or toml_product or crate_name
    resolved_identifier = identifier or toml_identifier
    if resolved_identifier is None:
        resolved_identifier = f'com.example.{crate_name}'
        l.warning(
            "pyshade init: 未找到 identifier,使用占位 {}(发布前请以 --identifier 或 Tauri.toml 提供)",
            resolved_identifier,
        )
    title, width, height = toml_window or (resolved_product, 800, 600)

    params = InitParams(
        crate_name=crate_name,
        lib_name=lib_name,
        pkg_name=pkg_name,
        product_name=resolved_product,
        identifier=resolved_identifier,
        version=resolved_version,
        window_title=title or resolved_product,
        window_width=width,
        window_height=height,
    )
    _validate_params(params)
    return params


def _render_params(params: InitParams) -> dict[str, str]:
    from pyshade import __version__

    return {
        'crate_name': params.crate_name,
        'lib_name': params.lib_name,
        'pkg_name': params.pkg_name,
        'product_name': params.product_name,
        'identifier': params.identifier,
        'version': params.version,
        # 自由文本按目标格式转义(JSON):title 含引号等字符照样渲染出合法 tauri.conf.json
        'window_title_json': json.dumps(params.window_title, ensure_ascii=False),
        'window_width': str(params.window_width),
        'window_height': str(params.window_height),
        'pyshade_version': __version__,
    }


def init_project(
    project_dir: Path,
    *,
    package: str | None = None,
    product_name: str | None = None,
    identifier: str | None = None,
    version: str | None = None,
    force: bool = False,
) -> InitResult:
    """生成 <project_dir>/src-tauri/;返回创建与跳过清单。"""
    project_dir = project_dir.absolute()
    params = infer_params(
        project_dir, package=package, product_name=product_name, identifier=identifier, version=version
    )
    replacements = _render_params(params)
    templates = resources.files('pyshade.packager') / '_templates' / 'src-tauri'
    out_root = project_dir / 'src-tauri'

    created: list[Path] = []
    skipped: list[Path] = []
    for source_rel, dest_rel, needs_render in _MANIFEST:
        dest = out_root / dest_rel
        if dest.exists() and not force:
            skipped.append(dest)
            continue
        source = templates
        for part in source_rel.split('/'):
            source = source / part
        dest.parent.mkdir(parents=True, exist_ok=True)
        if needs_render:
            dest.write_text(render(source.read_text(encoding='utf-8'), replacements), encoding='utf-8', newline='\n')
        else:
            dest.write_bytes(source.read_bytes())
        created.append(dest)

    if skipped:
        l.info(
            "pyshade init: {} 个文件已存在被跳过(--force 覆盖):{}",
            len(skipped),
            [str(p.relative_to(project_dir)) for p in skipped],
        )
    l.info(
        "pyshade init: src-tauri 就绪({} 个文件);默认图标为占位图,发布前请替换 icons/ 并保持文件名;"
        "建议把 src-tauri/pyembed 与 src-tauri/target 加进 pyright exclude",
        len(created),
    )
    return InitResult(src_tauri_dir=out_root, created=created, skipped=skipped)
