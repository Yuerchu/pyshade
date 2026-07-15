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
        watch=args.watch,
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
    bundle_parser.add_argument('--watch', action='store_true', help='esbuild watch 模式(TS 变更即重打)')
    bundle_parser.add_argument('--workdir', default='.pyshade/build', help='staging 工作目录')

    testkit_parser = sub.add_parser('bundle-testkit', help='内部:testkit 的 esbuild 构建(CI 对照实验)')
    testkit_parser.add_argument('--out', default='frontend/dist-testkit/testkit.js', help='输出文件')

    init_parser = sub.add_parser('init', help='生成 src-tauri 打包工程(standalone 安装包,配合 pyshade package)')
    init_parser.add_argument('--dir', default='.', help='项目根(pyproject.toml 所在)')
    init_parser.add_argument('--package', default=None, help='src 布局下的包名(src/ 下多包时必填)')
    init_parser.add_argument('--product-name', default=None, help='安装包产品名(缺省读 Tauri.toml 或用发行名)')
    init_parser.add_argument('--identifier', default=None, help='应用标识(如 cn.example.myapp;缺省读 Tauri.toml)')
    init_parser.add_argument('--force', action='store_true', help='覆盖已存在的文件')

    args = parser.parse_args()
    if args.command == 'build':
        _build(args)
    elif args.command == 'init':
        _init(args)
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
