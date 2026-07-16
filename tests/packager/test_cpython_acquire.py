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


def _fake_pyembed_tarball(
    *,
    evil_member: str | None = None,
    extra_infos: tuple[tarfile.TarInfo, ...] = (),
) -> bytes:
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
        for info in extra_infos:
            tar.addfile(info)
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

    def test_dotdot_inside_whitelist_rejected(self, tmp_path: Path) -> None:
        # startswith('python/') 拦不住的形态:白名单漏洞的定点回归
        tarball = tmp_path / 'evil.tar.gz'
        tarball.write_bytes(_fake_pyembed_tarball(evil_member='python/../../evil.txt'))
        with pytest.raises(CpythonAcquireError, match='路径逃逸'):
            extract_pyembed(tarball, tmp_path / 'pyembed')

    def test_device_member_rejected(self, tmp_path: Path) -> None:
        device = tarfile.TarInfo('python/dev-null')
        device.type = tarfile.CHRTYPE
        tarball = tmp_path / 'evil.tar.gz'
        tarball.write_bytes(_fake_pyembed_tarball(extra_infos=(device,)))
        with pytest.raises(CpythonAcquireError, match='设备/FIFO'):
            extract_pyembed(tarball, tmp_path / 'pyembed')

    def test_escaping_symlink_rejected(self, tmp_path: Path) -> None:
        link = tarfile.TarInfo('python/lib/escape')
        link.type = tarfile.SYMTYPE
        link.linkname = '../../outside'
        tarball = tmp_path / 'evil.tar.gz'
        tarball.write_bytes(_fake_pyembed_tarball(extra_infos=(link,)))
        with pytest.raises(CpythonAcquireError, match='之外'):
            extract_pyembed(tarball, tmp_path / 'pyembed')

    def test_absolute_symlink_rejected(self, tmp_path: Path) -> None:
        link = tarfile.TarInfo('python/lib/abs')
        link.type = tarfile.SYMTYPE
        link.linkname = '/etc/passwd'
        tarball = tmp_path / 'evil.tar.gz'
        tarball.write_bytes(_fake_pyembed_tarball(extra_infos=(link,)))
        with pytest.raises(CpythonAcquireError, match='之外'):
            extract_pyembed(tarball, tmp_path / 'pyembed')

    @pytest.mark.skipif(_IS_WINDOWS, reason='symlink 落盘需要 unix')
    def test_internal_symlink_allowed(self, tmp_path: Path) -> None:
        link = tarfile.TarInfo('python/bin/python')
        link.type = tarfile.SYMTYPE
        link.linkname = 'python3'  # PBS unix 布局的真实形态
        tarball = tmp_path / 'ok.tar.gz'
        tarball.write_bytes(_fake_pyembed_tarball(extra_infos=(link,)))
        pyembed = tmp_path / 'pyembed'
        extract_pyembed(tarball, pyembed)
        assert (pyembed / 'python' / 'bin' / 'python').is_symlink()

    @pytest.mark.filterwarnings('ignore::DeprecationWarning')  # 3.12+ 对无 filter 的 extractall 告警:此处刻意模拟老 API
    def test_legacy_python_without_tar_filter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """PEP 706 兼容:3.10.0-3.10.11/3.11.0-3.11.3 无 filter 参数(传入即 TypeError)。

        spy 复刻老签名(收到 filter kwarg 即抛),比 delattr(tarfile, 'data_filter') 更强。
        """
        monkeypatch.setattr(_cpython, '_tar_supports_filter', lambda: False)
        original = tarfile.TarFile.extractall

        def legacy_extractall(self: tarfile.TarFile, *args: object, **kwargs: object) -> None:
            if 'filter' in kwargs:
                raise TypeError("extractall() got an unexpected keyword argument 'filter'")
            original(self, *args, **kwargs)  # pyright: ignore[reportArgumentType]

        monkeypatch.setattr(tarfile.TarFile, 'extractall', legacy_extractall)

        tarball = tmp_path / 'cpython.tar.gz'
        tarball.write_bytes(_fake_pyembed_tarball())
        pyembed = tmp_path / 'pyembed'
        python = extract_pyembed(tarball, pyembed)  # 正常包解压成功
        assert python.read_bytes() == b'fake-python'

        evil = tmp_path / 'evil.tar.gz'
        evil.write_bytes(_fake_pyembed_tarball(evil_member='python/../../evil.txt'))
        with pytest.raises(CpythonAcquireError, match='路径逃逸'):  # 恶意包照样被前置校验拦下
            extract_pyembed(evil, tmp_path / 'pyembed2')

    def test_disk_error_wrapped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(self: tarfile.TarFile, *args: object, **kwargs: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(tarfile.TarFile, 'extractall', boom)
        tarball = tmp_path / 'cpython.tar.gz'
        tarball.write_bytes(_fake_pyembed_tarball())
        with pytest.raises(CpythonAcquireError, match='解压失败'):
            extract_pyembed(tarball, tmp_path / 'pyembed')

    def test_missing_stamp_returns_none(self, tmp_path: Path) -> None:
        assert read_pyembed_stamp(tmp_path) is None
