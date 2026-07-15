"""pyshade CLI:build(编译到目录,vite/框架开发管线)与 bundle(零 Node 用户管线)。"""

import argparse
import importlib
import sys
from pathlib import Path

from pyshade.app import ShadeApp
from pyshade.compiler import compile_app


def load_app(spec: str) -> ShadeApp:
    """解析 '模块路径[:属性]'(默认属性 app)并返回 ShadeApp 实例;失败即 SystemExit。"""
    module_path, _, attr = spec.rpartition(':')
    if not module_path:
        module_path, attr = attr, 'app'
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        print(f"无法导入模块 {module_path!r}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    app_obj = getattr(module, attr, None)
    if not isinstance(app_obj, ShadeApp):
        print(f"{module_path}:{attr} 不是 ShadeApp 实例", file=sys.stderr)
        raise SystemExit(1)
    return app_obj


def _build(args: argparse.Namespace) -> None:
    app_obj = load_app(args.app)
    out_dir = Path(args.out)
    compile_app(app_obj, out_dir)
    print(f"编译完成 → {out_dir.resolve()}")


def _bundle(args: argparse.Namespace) -> None:
    from pyshade.bundler import bundle_app

    app_obj = load_app(args.app)
    result = bundle_app(
        app_obj,
        args.out,
        dev=args.dev,
        workdir=args.workdir,
    )
    print(f"打包完成 → {result.out_dir}(app.js {result.app_js_bytes / 1024:.0f} KB)")


def _init(args: argparse.Namespace) -> None:
    from pyshade.packager._scaffold import ScaffoldError, init_project

    try:
        result = init_project(
            Path(args.dir),
            package=args.package,
            product_name=args.product_name,
            identifier=args.identifier,
            force=args.force,
        )
    except ScaffoldError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"src-tauri 就绪 → {result.src_tauri_dir}(新建 {len(result.created)},跳过 {len(result.skipped)})")


def _package(args: argparse.Namespace) -> None:
    from pyshade.packager import CpythonAcquireError, package_app
    from pyshade.packager._pyembed import PyembedInstallError
    from pyshade.packager._tauri_cli import TauriCliError

    try:
        result = package_app(
            args.app,
            Path(args.dir),
            out_dir=Path(args.out),
            bundles=tuple(args.bundles.split(',')) if args.bundles else None,
            profile=args.profile,
            extra_requirements=tuple(args.with_requirements),
            package=args.package,
            skip_bundle=args.skip_bundle,
            fresh_pyembed=args.fresh_pyembed,
            python_version=args.python_version,
            pbs_release=args.pbs_release,
        )
    except (TauriCliError, CpythonAcquireError, PyembedInstallError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"安装包就绪 → {Path(args.out).resolve()}({len(result.artifacts)} 个产物;裸可执行 {result.binary})")


def main() -> None:
    parser = argparse.ArgumentParser(prog='pyshade', description='PyShade 构建工具')
    sub = parser.add_subparsers(dest='command')

    build_parser = sub.add_parser('build', help='编译 ShadeApp 到前端产物(框架开发/vite 管线)')
    build_parser.add_argument('app', help='模块路径:属性名(如 myapp.app:app)')
    build_parser.add_argument('--out', default='frontend/src/generated', help='输出目录')

    bundle_parser = sub.add_parser('bundle', help='零 Node 打包:产出 pytauri 可用的 frontendDist')
    bundle_parser.add_argument('app', help='模块路径:属性名(如 myapp.app:app)')
    bundle_parser.add_argument('--out', default='dist', help='输出目录(index.html + app.js + style.css)')
    bundle_parser.add_argument('--dev', action='store_true', help='开发构建:sourcemap + React 开发警告,不 minify')
    bundle_parser.add_argument('--workdir', default='.pyshade/build', help='staging 工作目录')

    testkit_parser = sub.add_parser('bundle-testkit', help='内部:testkit 的 esbuild 构建(CI 对照实验)')
    testkit_parser.add_argument('--out', default='frontend/dist-testkit/testkit.js', help='输出文件')

    init_parser = sub.add_parser('init', help='生成 src-tauri 打包工程(standalone 安装包,配合 pyshade package)')
    init_parser.add_argument('--dir', default='.', help='项目根(pyproject.toml 所在)')
    init_parser.add_argument('--package', default=None, help='src 布局下的包名(src/ 下多包时必填)')
    init_parser.add_argument('--product-name', default=None, help='安装包产品名(缺省读 Tauri.toml 或用发行名)')
    init_parser.add_argument('--identifier', default=None, help='应用标识(如 cn.example.myapp;缺省读 Tauri.toml)')
    init_parser.add_argument('--force', action='store_true', help='覆盖已存在的文件')

    package_parser = sub.add_parser('package', help='standalone 打包:便携 CPython + cargo-tauri 出安装包')
    package_parser.add_argument('app', help='模块路径:属性名(如 myapp.app:app)')
    package_parser.add_argument('--dir', default='.', help='项目根(含 src-tauri/,先 pyshade init)')
    package_parser.add_argument('--out', default='dist-package', help='安装包输出目录')
    package_parser.add_argument(
        '--bundles', default=None, help="逗号分隔的 bundle 类型(缺省按平台:nsis,msi / dmg,app / deb)"
    )
    package_parser.add_argument('--profile', default='bundle-release', choices=['bundle-release', 'bundle-dev'])
    package_parser.add_argument(
        '--with',
        dest='with_requirements',
        action='append',
        default=[],
        metavar='REQ',
        help='追加 requirement(本地 wheel/目录)',
    )
    package_parser.add_argument('--package', default=None, help='src 布局下的包名(src/ 下多包时必填)')
    package_parser.add_argument('--skip-bundle', action='store_true', help='跳过前端 bundle(已自备 src-tauri/frontend)')
    package_parser.add_argument('--fresh-pyembed', action='store_true', help='强制重建内嵌解释器')
    package_parser.add_argument('--python-version', default=None, help='便携 CPython 版本(缺省用 pin 值)')
    package_parser.add_argument('--pbs-release', default=None, help='python-build-standalone release 标签')

    dev_parser = sub.add_parser('dev', help='开发模式:监听源码 → 重编译 → 浏览器自动刷新(HTTP,不开原生窗口)')
    dev_parser.add_argument('app', help='模块路径:属性名(如 myapp.app:app)')
    dev_parser.add_argument('--port', type=int, default=8765, help='dev server 端口')
    dev_parser.add_argument('--open', action='store_true', help='启动后打开浏览器')
    dev_parser.add_argument('--watch', action='append', default=[], metavar='PATH', help='追加监听目录')
    dev_parser.add_argument('--workdir', default='.pyshade/dev', help='dev 工作目录')

    args = parser.parse_args()
    if args.command == 'package':
        from pyshade.packager import CPYTHON_VERSION, PBS_RELEASE

        args.python_version = args.python_version or CPYTHON_VERSION
        args.pbs_release = args.pbs_release or PBS_RELEASE
    if args.command == 'build':
        _build(args)
    elif args.command == 'init':
        _init(args)
    elif args.command == 'package':
        _package(args)
    elif args.command == 'dev':
        from pyshade.dev import run_dev

        raise SystemExit(
            run_dev(
                args.app,
                port=args.port,
                open_browser=args.open,
                watch=[Path(p) for p in args.watch],
                workdir=Path(args.workdir),
            )
        )
    elif args.command == 'bundle':
        _bundle(args)
    elif args.command == 'bundle-testkit':
        from pyshade.bundler import bundle_testkit

        out_path = bundle_testkit(args.out)
        print(f"testkit 构建完成 → {out_path}")
    else:
        parser.print_help()
        raise SystemExit(1)


if __name__ == '__main__':
    main()
