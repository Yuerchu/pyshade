"""便携 CPython 获取:triple 映射、pin 表、缓存、伪 tarball 解压/校验/逃逸拒绝(全部不联网)。"""

import hashlib
import io
import platform
import tarfile
from pathlib import Path

import pytest

from pyshade.packager import _cpython
from pyshade.packager._cpython import (
    CpythonAcquireError,
    cpython_triple,
    ensure_cpython_tarball,
    extract_pyembed,
    pyembed_python_path,
    pyembed_stamp,
    read_pyembed_stamp,
    tarball_url,
)

_IS_WINDOWS = platform.system().lower() == 'windows'


def _fake_pyembed_tarball(*, evil_member: str | None = None) -> bytes:
    """内含 python/<解释器> 的最小 tarball(与 PBS install_only 布局同形)。"""
    interpreter = 'python/python.exe' if _IS_WINDOWS else 'python/bin/python3'
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        for name, payload in ((interpreter, b'fake-python'), ('python/LICENSE.txt', b'PSF')):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        if evil_member is not None:
            info = tarfile.TarInfo(evil_member)
            info.size = 4
            tar.addfile(info, io.BytesIO(b'evil'))
    return buffer.getvalue()


class TestTriple:
    def test_current_platform_supported(self) -> None:
        assert cpython_triple() in _cpython._TARBALL_SHA256  # pyright: ignore[reportPrivateUsage]

    def test_all_platforms_pinned(self) -> None:
        # 发版纪律:六平台 sha 全部就位(scripts/pin_cpython.py)
        table = _cpython._TARBALL_SHA256  # pyright: ignore[reportPrivateUsage]
        assert len(table) == 6
        assert all(len(sha) == 64 for sha in table.values())

    def test_url_shape(self) -> None:
        url = tarball_url('x86_64-pc-windows-msvc')
        assert url == (
            'https://github.com/astral-sh/python-build-standalone/releases/download/'
            f'{_cpython.PBS_RELEASE}/cpython-{_cpython.CPYTHON_VERSION}+{_cpython.PBS_RELEASE}'
            '-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
        )

    def test_mirror_env_in_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('PYSHADE_CPYTHON_MIRROR', 'https://mirror.example.com/pbs/')
        assert tarball_url('x86_64-apple-darwin').startswith('https://mirror.example.com/pbs/')


class TestEnsureTarball:
    def test_archive_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        blob = _fake_pyembed_tarball()
        archive = tmp_path / 'cpython.tar.gz'
        archive.write_bytes(blob)
        monkeypatch.setenv('PYSHADE_CPYTHON_ARCHIVE', str(archive))
        monkeypatch.setitem(
            _cpython._TARBALL_SHA256,  # pyright: ignore[reportPrivateUsage]
            cpython_triple(),
            hashlib.sha256(blob).hexdigest(),
        )
        assert ensure_cpython_tarball() == archive

    def test_archive_override_missing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv('PYSHADE_CPYTHON_ARCHIVE', str(tmp_path / 'nope.tar.gz'))
        with pytest.raises(CpythonAcquireError, match='不存在'):
            ensure_cpython_tarball()

    def test_archive_override_tampered(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        archive = tmp_path / 'cpython.tar.gz'
        archive.write_bytes(b'tampered')
        monkeypatch.setenv('PYSHADE_CPYTHON_ARCHIVE', str(archive))
        with pytest.raises(CpythonAcquireError, match='校验失败'):
            ensure_cpython_tarball()

    def test_cache_hit_skips_download(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv('PYSHADE_CACHE_DIR', str(tmp_path))
        triple = cpython_triple()
        cached = (
            tmp_path / 'cpython' / f'{_cpython.CPYTHON_VERSION}+{_cpython.PBS_RELEASE}' / _cpython.tarball_name(triple)
        )
        cached.parent.mkdir(parents=True)
        cached.write_bytes(b'cached')

        def boom(url: str) -> bytes:
            raise AssertionError('缓存命中不应下载')

        monkeypatch.setattr(_cpython, '_download', boom)
        assert ensure_cpython_tarball() == cached

    def test_download_verify_and_place(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv('PYSHADE_CACHE_DIR', str(tmp_path))
        blob = _fake_pyembed_tarball()

        def fake_download(url: str) -> bytes:
            return blob

        monkeypatch.setattr(_cpython, '_download', fake_download)
        monkeypatch.setitem(
            _cpython._TARBALL_SHA256,  # pyright: ignore[reportPrivateUsage]
            cpython_triple(),
            hashlib.sha256(blob).hexdigest(),
        )
        result = ensure_cpython_tarball()
        assert result.read_bytes() == blob

    def test_sha_mismatch_rejected(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv('PYSHADE_CACHE_DIR', str(tmp_path))

        def fake_download(url: str) -> bytes:
            return b'tampered'

        monkeypatch.setattr(_cpython, '_download', fake_download)
        with pytest.raises(CpythonAcquireError, match='校验失败'):
            ensure_cpython_tarball()

    def test_custom_version_without_pin_warns_not_fails(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv('PYSHADE_CACHE_DIR', str(tmp_path))
        blob = _fake_pyembed_tarball()

        def fake_download(url: str) -> bytes:
            return blob

        monkeypatch.setattr(_cpython, '_download', fake_download)
        result = ensure_cpython_tarball(version='3.14.0', release='20990101')
        assert result.is_file()

    def test_custom_version_with_env_sha(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv('PYSHADE_CACHE_DIR', str(tmp_path))
        blob = _fake_pyembed_tarball()
        monkeypatch.setenv('PYSHADE_CPYTHON_SHA256', hashlib.sha256(b'other').hexdigest())

        def fake_download(url: str) -> bytes:
            return blob

        monkeypatch.setattr(_cpython, '_download', fake_download)
        with pytest.raises(CpythonAcquireError, match='校验失败'):
            ensure_cpython_tarball(version='3.14.0', release='20990101')


class TestExtract:
    def test_extract_and_stamp(self, tmp_path: Path) -> None:
        tarball = tmp_path / 'cpython.tar.gz'
        tarball.write_bytes(_fake_pyembed_tarball())
        pyembed = tmp_path / 'pyembed'
        python = extract_pyembed(tarball, pyembed)
        assert python == pyembed_python_path(pyembed)
        assert python.read_bytes() == b'fake-python'
        assert read_pyembed_stamp(pyembed) == pyembed_stamp(cpython_triple())

    def test_extract_replaces_existing(self, tmp_path: Path) -> None:
        tarball = tmp_path / 'cpython.tar.gz'
        tarball.write_bytes(_fake_pyembed_tarball())
        pyembed = tmp_path / 'pyembed'
        (pyembed / 'python').mkdir(parents=True)
        (pyembed / 'python' / 'stale.txt').write_text('old', encoding='utf-8')
        extract_pyembed(tarball, pyembed)
        assert not (pyembed / 'python' / 'stale.txt').exists()

    def test_member_escape_rejected(self, tmp_path: Path) -> None:
        tarball = tmp_path / 'evil.tar.gz'
        tarball.write_bytes(_fake_pyembed_tarball(evil_member='outside.txt'))
        with pytest.raises(CpythonAcquireError, match='预期外成员'):
            extract_pyembed(tarball, tmp_path / 'pyembed')

    def test_missing_stamp_returns_none(self, tmp_path: Path) -> None:
        assert read_pyembed_stamp(tmp_path) is None
