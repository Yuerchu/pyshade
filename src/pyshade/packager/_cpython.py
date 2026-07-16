"""便携 CPython 获取:python-build-standalone tarball 下载 + 用户级缓存(镜像 _esbuild.py)。

与 esbuild 不同,校验对象是 tarball 本身:PBS 走 GitHub 直链无镜像重打包问题,
官方 SHA256SUMS 即 tarball 摘要,直接对齐。
env:PYSHADE_CPYTHON_MIRROR(替换下载前缀)/ PYSHADE_CPYTHON_ARCHIVE(离线 tarball)/
PYSHADE_CPYTHON_SHA256(自选版本时的校验值)/ PYSHADE_CACHE_DIR。

版本策略:固定 pin 单版本,与打包机 Python 解耦(打包机 3.10 也产 3.13 运行时);
自选版本经 --python-version/--pbs-release 逃生口,无 pin 值降级 warn。
"""

import hashlib
import http.client
import os
import platform
import posixpath
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from loguru import logger as l

from pyshade._cache import cache_root

CPYTHON_VERSION = '3.13.14'
PBS_RELEASE = '20260623'

# scripts/pin_cpython.py 生成;升级 CPython pin 时整表更新
_TARBALL_SHA256: dict[str, str] = {
    'x86_64-pc-windows-msvc': '7c3159205dda0289a47e6dd1226c4e5800b1f99a03146cdc25a41fed8ef74f5a',
    'aarch64-pc-windows-msvc': 'dc339c8d47f0a28b582859f62ba7efe862cd6d184af02acf36090124fac99698',
    'x86_64-apple-darwin': 'fdbe7198fb32f24ab99c67cb68cb265615e0bb6cb6586ffccb629ef9ca868420',
    'aarch64-apple-darwin': '795a5aeeb050f00aa8a2214d779bad9f1b9113edb6923317a80c042a11a087d7',
    'x86_64-unknown-linux-gnu': '459ed79967acc207bef2ff5124dac35d74d5108528e37b15395d14e2922f2c92',
    'aarch64-unknown-linux-gnu': 'e931d7a393f54902503f8745ceb35420e7dd50a067e78e5f45c71404f7a15b30',
}

_TRIPLE_MAP: dict[tuple[str, str], str] = {
    ('windows', 'amd64'): 'x86_64-pc-windows-msvc',
    ('windows', 'arm64'): 'aarch64-pc-windows-msvc',
    ('darwin', 'x86_64'): 'x86_64-apple-darwin',
    ('darwin', 'arm64'): 'aarch64-apple-darwin',
    ('linux', 'x86_64'): 'x86_64-unknown-linux-gnu',
    ('linux', 'aarch64'): 'aarch64-unknown-linux-gnu',
}

DEFAULT_BASE = 'https://github.com/astral-sh/python-build-standalone/releases/download'

_SELF_HELP = (
    "自救路径:\n"
    "  1) 设置 HTTPS_PROXY 走代理\n"
    "  2) 设置 PYSHADE_CPYTHON_MIRROR 指向镜像前缀(替换 GitHub releases 前缀)\n"
    "  3) 手动下载 install_only_stripped tarball 后设置 PYSHADE_CPYTHON_ARCHIVE 指向该文件"
)


class CpythonAcquireError(RuntimeError):
    """便携 CPython 获取失败;错误信息附自救路径。"""


def cpython_triple() -> str:
    key = (platform.system().lower(), platform.machine().lower())
    triple = _TRIPLE_MAP.get(key)
    if triple is None:
        raise CpythonAcquireError(f"不支持的平台 {key};请手动下载 PBS tarball 并设置 PYSHADE_CPYTHON_ARCHIVE")
    return triple


def tarball_name(triple: str, *, version: str = CPYTHON_VERSION, release: str = PBS_RELEASE) -> str:
    return f'cpython-{version}+{release}-{triple}-install_only_stripped.tar.gz'


def tarball_url(triple: str, *, version: str = CPYTHON_VERSION, release: str = PBS_RELEASE) -> str:
    base = os.environ.get('PYSHADE_CPYTHON_MIRROR', DEFAULT_BASE).rstrip('/')
    return f'{base}/{release}/{tarball_name(triple, version=version, release=release)}'


def pyembed_stamp(triple: str, *, version: str = CPYTHON_VERSION, release: str = PBS_RELEASE) -> str:
    """pyembed 目录的身份标识:增量判断依据(版本/平台变更即重建)。"""
    return f'cpython-{version}+{release}-{triple}'


def _expected_sha256(triple: str, *, version: str, release: str) -> str:
    if version == CPYTHON_VERSION and release == PBS_RELEASE:
        return _TARBALL_SHA256.get(triple, '')
    return os.environ.get('PYSHADE_CPYTHON_SHA256', '')


def _download(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(url, timeout=300) as response:
                return response.read()
        # OSError 覆盖 URLError/ConnectionResetError/TimeoutError;HTTPException 覆盖
        # 读 body 中途断流的 IncompleteRead(最常见的真实失败形态,此前裸抛不重试)
        except (OSError, http.client.HTTPException) as exc:
            last_error = exc
            l.warning("pyshade.packager: 下载失败(第 {} 次): {}", attempt, exc)
    raise CpythonAcquireError(f"便携 CPython 下载失败: {url}\n{_SELF_HELP}") from last_error


def _verify(blob: bytes, triple: str, *, version: str, release: str) -> None:
    expected = _expected_sha256(triple, version=version, release=release)
    actual = hashlib.sha256(blob).hexdigest()
    if expected and actual != expected:
        raise CpythonAcquireError(
            f"CPython tarball 校验失败(triple={triple}):期望 {expected},实际 {actual};"
            "下载源内容可能被篡改,请改用官方源或核对 PYSHADE_CPYTHON_MIRROR"
        )
    if not expected:
        l.warning("pyshade.packager: {} 无 pin 校验值,跳过校验(sha256={})", triple, actual)


def ensure_cpython_tarball(*, version: str = CPYTHON_VERSION, release: str = PBS_RELEASE) -> Path:
    """返回本地 tarball 路径:env 覆盖 → 缓存命中 → 下载校验落位。"""
    override = os.environ.get('PYSHADE_CPYTHON_ARCHIVE')
    if override:
        path = Path(override)
        if not path.is_file():
            raise CpythonAcquireError(f"PYSHADE_CPYTHON_ARCHIVE 指向的文件不存在: {path}")
        _verify(path.read_bytes(), cpython_triple(), version=version, release=release)
        return path

    triple = cpython_triple()
    target = cache_root() / 'cpython' / f'{version}+{release}' / tarball_name(triple, version=version, release=release)
    if target.is_file():
        return target

    url = tarball_url(triple, version=version, release=release)
    l.info("pyshade.packager: 下载便携 CPython {} ({})", version, url)
    blob = _download(url)
    _verify(blob, triple, version=version, release=release)

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
        tmp.write(blob)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, target)
    return target


def pyembed_python_path(pyembed_dir: Path) -> Path:
    """内嵌解释器路径(win: python/python.exe;unix: python/bin/python3)。"""
    if platform.system().lower() == 'windows':
        return pyembed_dir / 'python' / 'python.exe'
    return pyembed_dir / 'python' / 'bin' / 'python3'


def _tar_supports_filter() -> bool:
    """PEP 706 特性检测:filter= 参数 3.10.12/3.11.4 才 backport,3.10.0-3.10.11/
    3.11.0-3.11.3 传入即 TypeError。函数化便于测试注入旧环境。"""
    return hasattr(tarfile, 'data_filter')


def _validate_member(member: tarfile.TarInfo) -> None:
    """逐成员安全校验(全版本都跑):白名单前缀 + 路径逃逸 + 类型 + 链接目标。

    无 filter 的老 Python 上这是唯一防线;有 filter 时叠加官方防护(filter='tar'
    不拦链接目标逃逸,链接校验在此补齐)。unix 必须保留 symlink(libpython),
    故校验目标而非剥离链接。
    """
    name = member.name[2:] if member.name.startswith('./') else member.name
    if not (name == 'python' or name.startswith('python/')):
        raise CpythonAcquireError(f"tarball 含预期外成员 {member.name},拒绝解压(防路径逃逸)")
    if '..' in name.split('/') or posixpath.isabs(name) or '\\' in name:
        # startswith('python/') 拦不住 'python/../../evil'
        raise CpythonAcquireError(f"tarball 成员 {member.name} 含路径逃逸(../ 或绝对路径),拒绝解压")
    if not (member.isreg() or member.isdir() or member.issym() or member.islnk()):
        raise CpythonAcquireError(f"tarball 成员 {member.name} 是设备/FIFO 类型,拒绝解压")
    if member.issym() or member.islnk():
        linkname = member.linkname
        if member.issym():
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), linkname))
        else:  # hardlink 目标是归档内路径,相对归档根
            resolved = posixpath.normpath(linkname)
        inside = resolved == 'python' or resolved.startswith('python/')
        if posixpath.isabs(linkname) or '\\' in linkname or not inside:
            raise CpythonAcquireError(f"tarball 链接成员 {member.name} → {linkname} 指向解压目录之外,拒绝解压")


def extract_pyembed(
    tarball: Path,
    pyembed_dir: Path,
    *,
    version: str = CPYTHON_VERSION,
    release: str = PBS_RELEASE,
) -> Path:
    """解压 tarball 的 python/ 到 pyembed 目录,写 stamp;返回内嵌解释器路径。

    成员逐个过 _validate_member;解压按 Python 版本分支(PEP 706 兼容,见 _tar_supports_filter)。
    """
    if pyembed_dir.exists():
        shutil.rmtree(pyembed_dir)
    pyembed_dir.mkdir(parents=True)

    try:
        with tarfile.open(tarball, 'r:gz') as tar:
            for member in tar.getmembers():
                _validate_member(member)
            if _tar_supports_filter():
                tar.extractall(pyembed_dir, filter='tar')
            else:
                # 老版本无 filter 参数且传入即 TypeError:前置逐成员校验即等效防线
                tar.extractall(pyembed_dir)
    except (tarfile.TarError, OSError) as exc:
        raise CpythonAcquireError(
            f"tarball 解压失败({tarball} → {pyembed_dir}): {exc};磁盘空间/路径长度/权限问题也会走到这里"
        ) from exc

    python = pyembed_python_path(pyembed_dir)
    if not python.is_file():
        raise CpythonAcquireError(f"解压后未找到内嵌解释器: {python}")
    stamp = pyembed_dir / '.pyshade-stamp'
    stamp.write_text(pyembed_stamp(cpython_triple(), version=version, release=release), encoding='utf-8', newline='\n')
    return python


def read_pyembed_stamp(pyembed_dir: Path) -> str | None:
    """读取 pyembed 目录的 stamp(不存在返回 None);package 编排的增量判断入口。"""
    stamp = pyembed_dir / '.pyshade-stamp'
    if not stamp.is_file():
        return None
    return stamp.read_text(encoding='utf-8').strip()
