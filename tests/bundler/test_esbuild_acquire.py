"""esbuild 获取:平台映射、缓存路径、env 覆盖、伪 tarball 抽取与校验(全部不联网)。"""

import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from pyshade.bundler import _esbuild
from pyshade.bundler._esbuild import (
    EsbuildAcquireError,
    cache_root,
    ensure_esbuild,
    esbuild_platform,
)


def _fake_tarball(member: str, payload: bytes) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        info = tarfile.TarInfo(member)
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


class TestPlatform:
    def test_current_platform_supported(self) -> None:
        plat = esbuild_platform()
        assert plat in _esbuild._BINARY_SHA256  # pyright: ignore[reportPrivateUsage]

    def test_all_platforms_pinned(self) -> None:
        # 发版纪律:六平台 sha 全部就位(scripts/pin_esbuild.py)
        table = _esbuild._BINARY_SHA256  # pyright: ignore[reportPrivateUsage]
        assert len(table) == 6
        assert all(len(sha) == 64 for sha in table.values())

    def test_cache_dir_env_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv('PYSHADE_CACHE_DIR', str(tmp_path / 'x'))
        assert cache_root() == tmp_path / 'x'


class TestEnsureEsbuild:
    def test_esbuild_path_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        fake = tmp_path / 'esbuild.exe'
        fake.write_bytes(b'MZ')
        monkeypatch.setenv('PYSHADE_ESBUILD_PATH', str(fake))
        assert ensure_esbuild() == fake

    def test_esbuild_path_override_missing_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv('PYSHADE_ESBUILD_PATH', str(tmp_path / 'nope.exe'))
        with pytest.raises(EsbuildAcquireError, match='不存在'):
            ensure_esbuild()

    def test_cache_hit_skips_download(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv('PYSHADE_CACHE_DIR', str(tmp_path))
        plat = esbuild_platform()
        name = 'esbuild.exe' if plat.startswith('win32') else 'esbuild'
        cached = tmp_path / 'esbuild' / _esbuild.ESBUILD_VERSION / name
        cached.parent.mkdir(parents=True)
        cached.write_bytes(b'cached')

        def boom(url: str) -> bytes:
            raise AssertionError('缓存命中不应下载')

        monkeypatch.setattr(_esbuild, '_download', boom)
        assert ensure_esbuild() == cached

    def test_download_verify_and_place(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv('PYSHADE_CACHE_DIR', str(tmp_path))
        plat = esbuild_platform()
        member = _esbuild._binary_member(plat)  # pyright: ignore[reportPrivateUsage]
        payload = b'fake-esbuild-binary'
        blob = _fake_tarball(member, payload)

        def fake_download(url: str) -> bytes:
            return blob

        monkeypatch.setattr(_esbuild, '_download', fake_download)
        monkeypatch.setitem(
            _esbuild._BINARY_SHA256,  # pyright: ignore[reportPrivateUsage]
            plat,
            hashlib.sha256(payload).hexdigest(),
        )
        result = ensure_esbuild()
        assert result.read_bytes() == payload

    def test_sha_mismatch_rejected(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv('PYSHADE_CACHE_DIR', str(tmp_path))
        plat = esbuild_platform()
        member = _esbuild._binary_member(plat)  # pyright: ignore[reportPrivateUsage]
        blob = _fake_tarball(member, b'tampered')

        def fake_download(url: str) -> bytes:
            return blob

        monkeypatch.setattr(_esbuild, '_download', fake_download)
        with pytest.raises(EsbuildAcquireError, match='校验失败'):
            ensure_esbuild()

    def test_bad_tarball_rejected(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv('PYSHADE_CACHE_DIR', str(tmp_path))

        def fake_download(url: str) -> bytes:
            return b'not a tarball'

        monkeypatch.setattr(_esbuild, '_download', fake_download)
        with pytest.raises(EsbuildAcquireError, match='tarball'):
            ensure_esbuild()

    def test_registry_env_in_url(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv('PYSHADE_CACHE_DIR', str(tmp_path))
        monkeypatch.setenv('PYSHADE_NPM_REGISTRY', 'https://registry.npmmirror.com/')
        seen: list[str] = []

        def capture(url: str) -> bytes:
            seen.append(url)
            raise EsbuildAcquireError('stop')

        monkeypatch.setattr(_esbuild, '_download', capture)
        with pytest.raises(EsbuildAcquireError):
            ensure_esbuild()
        assert seen[0].startswith('https://registry.npmmirror.com/@esbuild/')
