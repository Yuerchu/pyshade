"""entry.tsx 与 tsconfig.json 发射(bundler 专用;vite 管线继续用手写 main.tsx)。"""

import json

from pyshade.app import ShadeApp
from pyshade.compiler.emit_page import SHADCN_MODULES


def emit_entry_tsx(app: ShadeApp) -> str:
    """main.tsx 的生成版;extra_components 逃生舱以 side-effect import 保住模块进图。"""
    lines = [
        '/* 由 pyshade bundler 生成 — 请勿手改。 */',
        'import { StrictMode } from "react";',
        'import { createRoot } from "react-dom/client";',
        'import App from "./generated/app.gen";',
    ]
    extra_modules: list[str] = []
    for component_cls in app.extra_components:
        tag = component_cls._shade_tag  # pyright: ignore[reportPrivateUsage]
        module = SHADCN_MODULES.get(tag, f'"@/components/ui/{tag.lower()}"')
        if module not in extra_modules:
            extra_modules.append(module)
    for module in extra_modules:
        lines.append(f'import {module};  // extra_components 逃生舱')
    lines += [
        '',
        'createRoot(document.getElementById("root")!).render(',
        '  <StrictMode>',
        '    <App />',
        '  </StrictMode>,',
        ');',
    ]
    return '\n'.join(lines) + '\n'


def emit_tsconfig() -> str:
    """esbuild 只消费 paths(@/* alias)与 jsx 设置;不用于 tsc。"""
    config = {
        'compilerOptions': {
            'jsx': 'react-jsx',
            'baseUrl': '.',
            'paths': {'@/*': ['./src/*']},
        }
    }
    return json.dumps(config, indent=2) + '\n'
