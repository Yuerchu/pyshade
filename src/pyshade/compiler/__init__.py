"""编译器(design.md §3.1、§3.6)。

Python DTO → React 代码生成;静态收集组件 import 生成 entry.tsx,交 esbuild 按需打包。
编译期校验:props 类型、组件嵌套合法性、事件签名、死引用。
"""

from pathlib import Path

from pyshade.app import ShadeApp
from pyshade.compiler.checks import check_app, check_page_ir
from pyshade.compiler.emit_app import emit_app, emit_manifest
from pyshade.compiler.emit_page import emit_page
from pyshade.compiler.emit_types import collect_enums, collect_item_models, emit_types
from pyshade.compiler.ir import PageIR, build_page_ir


def compile_app(app: ShadeApp, out_dir: str | Path) -> None:
    """编译 ShadeApp 到指定目录:pages/*.gen.tsx + app.gen.tsx + types.gen.ts + manifest.json。"""
    out = Path(out_dir)
    pages_dir = out / 'pages'
    pages_dir.mkdir(parents=True, exist_ok=True)

    page_irs: list[PageIR] = []
    for page in app.pages:
        page_ir = build_page_ir(page)
        check_page_ir(page_ir)
        page_irs.append(page_ir)
    check_app(page_irs)

    for page_ir in page_irs:
        tsx = emit_page(page_ir)
        (pages_dir / f'{page_ir.name}.gen.tsx').write_text(tsx, encoding='utf-8', newline='\n')

    enums = collect_enums(page_irs)
    item_models = collect_item_models(page_irs)
    extra_tags = [cls._shade_tag for cls in app.extra_components]  # pyright: ignore[reportPrivateUsage]
    (out / 'types.gen.ts').write_text(emit_types(enums, item_models), encoding='utf-8', newline='\n')
    (out / 'app.gen.tsx').write_text(emit_app(page_irs, keep_alive=app.keep_alive), encoding='utf-8', newline='\n')
    manifest = emit_manifest(page_irs, extra_components=extra_tags)
    (out / 'manifest.json').write_text(manifest, encoding='utf-8', newline='\n')
