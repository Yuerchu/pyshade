"""staging/entry/esbuild 参数与资产定位(不联网、不起 esbuild)。"""

import pytest

from pyshade.app import ShadeApp
from pyshade.bundler import esbuild_args
from pyshade.bundler._assets import locate_assets
from pyshade.bundler._entry import emit_entry_tsx, emit_tsconfig
from pyshade.components import Button, Switch, Text
from pyshade.page import Page


class EntryDemoPage(Page):
    heading = Text('hi')


def _app(**kwargs: object) -> ShadeApp:
    return ShadeApp(pages=[EntryDemoPage], **kwargs)  # pyright: ignore[reportArgumentType]


class TestEntry:
    def test_basic_entry_shape(self) -> None:
        entry = emit_entry_tsx(_app())
        assert 'import App from "./generated/app.gen";' in entry
        assert 'createRoot' in entry
        assert 'StrictMode' in entry
        assert '逃生舱' not in entry

    def test_extra_components_side_effect_imports(self) -> None:
        app = ShadeApp(pages=[EntryDemoPage], extra_components=[Button, Switch])
        entry = emit_entry_tsx(app)
        assert 'import "@/components/ui/button";' in entry
        assert 'import "@/components/ui/switch";' in entry

    def test_extra_components_dedup(self) -> None:
        app = ShadeApp(pages=[EntryDemoPage], extra_components=[Button, Button])
        entry = emit_entry_tsx(app)
        assert entry.count('"@/components/ui/button"') == 1

    def test_tsconfig_paths(self) -> None:
        import json

        config = json.loads(emit_tsconfig())
        assert config['compilerOptions']['paths'] == {'@/*': ['./src/*']}
        assert config['compilerOptions']['jsx'] == 'react-jsx'


class TestEsbuildArgs:
    def test_production_args(self) -> None:
        from pathlib import Path

        args = esbuild_args(entry='src/entry.tsx', outfile=Path('out/app.js'), dev=False, watch=False)
        assert '--bundle' in args
        assert '--format=esm' in args
        assert '--jsx=automatic' in args
        assert '--define:process.env.NODE_ENV="production"' in args
        assert '--minify' in args
        assert '--tsconfig=tsconfig.json' in args
        assert not any(a.startswith('--sourcemap') for a in args)

    def test_dev_args(self) -> None:
        from pathlib import Path

        args = esbuild_args(entry='src/entry.tsx', outfile=Path('out/app.js'), dev=True, watch=True)
        assert '--define:process.env.NODE_ENV="development"' in args
        assert '--sourcemap' in args
        assert '--minify' not in args
        assert '--watch=forever' in args


class TestAssets:
    def test_repo_layout_located(self) -> None:
        # 仓库内(editable install):应回退到 frontend/ 原地资产
        try:
            assets = locate_assets()
        except Exception as exc:  # 缺 dist-style 时给出可读跳过原因
            pytest.skip(f'资产缺件: {exc}')
        assert (assets.src_dir / 'runtime').is_dir()
        assert assets.node_modules.is_dir()
        assert assets.index_html.is_file()
