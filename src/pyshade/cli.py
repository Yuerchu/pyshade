"""pyshade CLI:build / dev 入口(design.md §3.6)。"""

import argparse
import importlib
import sys
from pathlib import Path

from pyshade.app import ShadeApp
from pyshade.compiler import compile_app


def _build(args: argparse.Namespace) -> None:
    module_path, _, attr = args.app.rpartition(':')
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
    out_dir = Path(args.out)
    compile_app(app_obj, out_dir)
    print(f"编译完成 → {out_dir.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(prog='pyshade', description='PyShade 构建工具')
    sub = parser.add_subparsers(dest='command')

    build_parser = sub.add_parser('build', help='编译 ShadeApp 到前端产物')
    build_parser.add_argument('app', help='模块路径:属性名(如 myapp.app:app)')
    build_parser.add_argument('--out', default='frontend/src/generated', help='输出目录')

    args = parser.parse_args()
    if args.command == 'build':
        _build(args)
    else:
        parser.print_help()
        raise SystemExit(1)
