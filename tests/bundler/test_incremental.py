"""bundle 窄版增量(M4):staging stamp 跳 copytree、esbuild 输入哈希跳全量构建、逃生口。

不联网不起真 esbuild:monkeypatch run_esbuild 计数并伪造 app.js 产物。
"""

from pathlib import Path
from typing import Any

import pytest

import pyshade.bundler as bundler
from pyshade.app import ShadeApp
from pyshade.bundler._assets import FrontendAssets
from pyshade.bundler._staging import prepare_staging, staging_stamp
from pyshade.components import Text
from pyshade.page import Page


class IncrementalProbePage(Page):
    hello = Text('incremental')


def _fake_assets(root: Path) -> FrontendAssets:
    src = root / 'frontend-src'
    for part in ('runtime', 'ipc', 'components', 'lib'):
        (src / part).mkdir(parents=True, exist_ok=True)
        (src / part / 'index.ts').write_text(f'// {part}\n', encoding='utf-8')
    (root / 'node_modules').mkdir(exist_ok=True)
    (root / 'index.html').write_text(
        '<head>\n    <link rel="stylesheet" href="./style.css" />\n'
        '    <script type="module" src="./app.js"></script>\n  </head>',
        encoding='utf-8',
    )
    (root / 'style.css').write_text(':root {}\n', encoding='utf-8')
    (root / 'vendor-manifest.json').write_text('{"react": "19.0.0"}\n', encoding='utf-8')
    return FrontendAssets(
        src_dir=src,
        node_modules=root / 'node_modules',
        style_css=root / 'style.css',
        index_html=root / 'index.html',
        vendor_stamp=root / 'vendor-manifest.json',
    )


@pytest.fixture
def assets(tmp_path: Path) -> FrontendAssets:
    return _fake_assets(tmp_path)


class TestStagingStamp:
    def test_stamp_stable_and_sensitive(self, assets: FrontendAssets) -> None:
        parts = ('runtime', 'ipc')
        first = staging_stamp(assets, parts)
        assert staging_stamp(assets, parts) == first
        target = assets.src_dir / 'runtime' / 'index.ts'
        target.write_text('// changed with different size\n', encoding='utf-8')
        assert staging_stamp(assets, parts) != first

    def test_prepare_skips_when_stamp_matches(self, assets: FrontendAssets, tmp_path: Path) -> None:
        work = tmp_path / 'work'
        prepare_staging(work, assets)
        canary = work / 'src' / 'runtime' / 'canary.txt'
        canary.write_text('留下来说明没有重拷\n', encoding='utf-8')
        prepare_staging(work, assets)
        assert canary.exists()  # 指纹命中 → copytree 被跳过

        (assets.src_dir / 'runtime' / 'index.ts').write_text('// framework changed!\n', encoding='utf-8')
        prepare_staging(work, assets)
        assert not canary.exists()  # 框架源码变了 → 重新铺 staging


class _EsbuildSpy:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, binary: Path, args: list[str], *, cwd: Path, env: dict[str, str]) -> None:
        self.calls += 1
        outfile = next(a for a in args if a.startswith('--outfile=')).removeprefix('--outfile=')
        Path(outfile).parent.mkdir(parents=True, exist_ok=True)
        Path(outfile).write_text(f'// build #{self.calls}\n', encoding='utf-8')


@pytest.fixture
def spy(assets: FrontendAssets, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _EsbuildSpy:
    instance = _EsbuildSpy()
    # fake esbuild 必须是真实文件:二进制身份(size/mtime)已纳入输入哈希
    fake_esbuild = tmp_path / 'esbuild-fake'
    fake_esbuild.write_text('#!/bin/true\n', encoding='utf-8')
    monkeypatch.setattr(bundler, 'locate_assets', lambda: assets)
    monkeypatch.setattr(bundler, 'ensure_esbuild', lambda: fake_esbuild)
    monkeypatch.setattr(bundler, 'run_esbuild', instance)
    monkeypatch.delenv('PYSHADE_BUNDLE_FRESH', raising=False)
    return instance


def _bundle(tmp_path: Path, **kwargs: Any) -> 'bundler.BundleResult':
    app = ShadeApp(pages=[IncrementalProbePage], **kwargs)
    return bundler.bundle_app(app, tmp_path / 'dist', workdir=tmp_path / 'work')


class TestEsbuildSkip:
    def test_second_build_skips(self, tmp_path: Path, spy: _EsbuildSpy) -> None:
        first = _bundle(tmp_path)
        assert spy.calls == 1 and first.esbuild_skipped is False
        second = _bundle(tmp_path)
        assert spy.calls == 1 and second.esbuild_skipped is True
        # index.html 每次照常重写(scheme boot script 在)
        assert 'data-pyshade-scheme' in (tmp_path / 'dist' / 'index.html').read_text(encoding='utf-8')

    def test_generated_change_rebuilds(self, tmp_path: Path, spy: _EsbuildSpy) -> None:
        _bundle(tmp_path)

        class IncrementalOtherPage(Page):
            hello = Text('changed output')

        app = ShadeApp(pages=[IncrementalOtherPage])
        result = bundler.bundle_app(app, tmp_path / 'dist', workdir=tmp_path / 'work')
        assert spy.calls == 2 and result.esbuild_skipped is False

    def test_staged_source_change_rebuilds(self, tmp_path: Path, spy: _EsbuildSpy, assets: FrontendAssets) -> None:
        _bundle(tmp_path)
        (assets.src_dir / 'runtime' / 'index.ts').write_text('// framework changed!\n', encoding='utf-8')
        result = _bundle(tmp_path)
        assert spy.calls == 2 and result.esbuild_skipped is False

    def test_dev_flag_change_rebuilds(self, tmp_path: Path, spy: _EsbuildSpy) -> None:
        _bundle(tmp_path)
        app = ShadeApp(pages=[IncrementalProbePage])
        result = bundler.bundle_app(app, tmp_path / 'dist', dev=True, workdir=tmp_path / 'work')
        assert spy.calls == 2 and result.esbuild_skipped is False

    def test_fresh_env_forces_rebuild(self, tmp_path: Path, spy: _EsbuildSpy, monkeypatch: pytest.MonkeyPatch) -> None:
        _bundle(tmp_path)
        monkeypatch.setenv('PYSHADE_BUNDLE_FRESH', '1')
        result = _bundle(tmp_path)
        assert spy.calls == 2 and result.esbuild_skipped is False

    def test_missing_outfile_rebuilds(self, tmp_path: Path, spy: _EsbuildSpy) -> None:
        _bundle(tmp_path)
        (tmp_path / 'dist' / 'app.js').unlink()
        result = _bundle(tmp_path)
        assert spy.calls == 2 and result.esbuild_skipped is False

    def test_vendor_stamp_change_rebuilds(self, tmp_path: Path, spy: _EsbuildSpy, assets: FrontendAssets) -> None:
        # 依赖升级(manifest/lockfile 内容变化)必须打掉哈希——此前只哈希 NODE_PATH 路径字符串,
        # 升级依赖后错跳 esbuild,持续输出陈旧 app.js
        _bundle(tmp_path)
        assets.vendor_stamp.write_text('{"react": "19.1.0"}\n', encoding='utf-8')
        result = _bundle(tmp_path)
        assert spy.calls == 2 and result.esbuild_skipped is False

    def test_esbuild_binary_change_rebuilds(
        self, tmp_path: Path, spy: _EsbuildSpy, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # PYSHADE_ESBUILD_PATH 换二进制:常量 ESBUILD_VERSION 感知不到,按 (path,size,mtime) 入哈希
        _bundle(tmp_path)
        other = tmp_path / 'esbuild-other'
        other.write_text('#!/bin/true # different binary\n', encoding='utf-8')
        monkeypatch.setattr(bundler, 'ensure_esbuild', lambda: other)
        result = _bundle(tmp_path)
        assert spy.calls == 2 and result.esbuild_skipped is False

    def test_corrupted_outfile_rebuilds(self, tmp_path: Path, spy: _EsbuildSpy) -> None:
        # 产物被外部截断/篡改:stamp 记 size,不静默复用损坏文件
        _bundle(tmp_path)
        outfile = tmp_path / 'dist' / 'app.js'
        outfile.write_text(outfile.read_text(encoding='utf-8') + '// corrupted\n', encoding='utf-8')
        result = _bundle(tmp_path)
        assert spy.calls == 2 and result.esbuild_skipped is False

    def test_fresh_forces_staging_recopy(
        self, tmp_path: Path, spy: _EsbuildSpy, assets: FrontendAssets, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 逃生口必须覆盖 staging:staged 树被破坏时指纹(只看资产源)仍命中,FRESH=1 要能恢复
        _bundle(tmp_path)
        staged = tmp_path / 'work' / 'src' / 'runtime' / 'index.ts'
        staged.unlink()
        monkeypatch.setenv('PYSHADE_BUNDLE_FRESH', '1')
        _bundle(tmp_path)
        assert staged.exists()

    def test_corrupt_staging_marker_recopies(self, tmp_path: Path, assets: FrontendAssets) -> None:
        work = tmp_path / 'work2'
        prepare_staging(work, assets)
        (work / '.staging-stamp').write_bytes(b'\xff\xfe\x00 broken')
        canary = work / 'src' / 'runtime' / 'canary.txt'
        canary.write_text('x\n', encoding='utf-8')
        prepare_staging(work, assets)  # 坏 marker 视为未命中 → 重拷,不炸
        assert not canary.exists()
