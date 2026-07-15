"""esbuild 官方二进制获取:npm registry tarball 裸 HTTPS 下载 + 用户级缓存。

版本 pin + 每平台二进制 sha256(校验解出的二进制而非 tarball——镜像重打包不受影响)。
env:PYSHADE_NPM_REGISTRY(国内镜像)/ PYSHADE_ESBUILD_PATH(离线兜底)/ PYSHADE_CACHE_DIR。
"""

import hashlib
import os
import platform
import stat
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from loguru import logger as l

ESBUILD_VERSION = '0.28.1'

# scripts/pin_esbuild.py 生成;升级 esbuild 版本时整表更新
_BINARY_SHA256: dict[str, str] = {
    'win32-x64': 'ec02ee9b14ab332416fedd10614dfb80eed5304d94f67745067c011934a8c3c3',
    'win32-arm64': 'bfb8798ab678f1ce4a723739f4a3eabab3244d7a04eeb12be2eb9f58095c13ef',
    'darwin-x64': 'dd53ccf32f9b5b3ab30d41388ef1fc8f81c44ca57ee7a32a7364a1753308d009',
    'darwin-arm64': 'e2dc9a52440a2a34f09434a2f4843cb1e30f84e40dcf238976ec61ef8cd7f36a',
    'linux-x64': '0c6588b092a2c291a72bab90659f3c9e0e25e0fe59c9ac12b4dae4d945e5548c',
    'linux-arm64': '51e829ba36f36be6d9aea6e329ddc4f9350302339b16aaca96a3cb97f64a8ebb',
}

_PLATFORM_MAP: dict[tuple[str, str], str] = {
    ('windows', 'amd64'): 'win32-x64',
    ('windows', 'arm64'): 'win32-arm64',
    ('darwin', 'x86_64'): 'darwin-x64',
    ('darwin', 'arm64'): 'darwin-arm64',
    ('linux', 'x86_64'): 'linux-x64',
    ('linux', 'aarch64'): 'linux-arm64',
}

DEFAULT_REGISTRY = 'https://registry.npmjs.org'


class EsbuildAcquireError(RuntimeError):
    """esbuild 二进制获取失败;错误信息附自救路径。"""


def esbuild_platform() -> str:
    key = (platform.system().lower(), platform.machine().lower())
    plat = _PLATFORM_MAP.get(key)
    if plat is None:
        raise EsbuildAcquireError(f"不支持的平台 {key};请手动下载 esbuild 并设置 PYSHADE_ESBUILD_PATH 指向该二进制")
    return plat


def cache_root() -> Path:
    override = os.environ.get('PYSHADE_CACHE_DIR')
    if override:
        return Path(override)
    system = platform.system().lower()
    if system == 'windows':
        base = os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))
        return Path(base) / 'pyshade'
    if system == 'darwin':
        return Path.home() / 'Library' / 'Caches' / 'pyshade'
    xdg = os.environ.get('XDG_CACHE_HOME')
    return (Path(xdg) if xdg else Path.home() / '.cache') / 'pyshade'


def _binary_member(plat: str) -> str:
    return 'package/esbuild.exe' if plat.startswith('win32') else 'package/bin/esbuild'


def _binary_name(plat: str) -> str:
    return 'esbuild.exe' if plat.startswith('win32') else 'esbuild'


def _download(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            l.warning("pyshade.bundler: 下载失败(第 {} 次): {}", attempt, exc)
    raise EsbuildAcquireError(
        f"esbuild 下载失败: {url}\n自救路径:\n"
        "  1) 国内网络设置 PYSHADE_NPM_REGISTRY=https://registry.npmmirror.com\n"
        "  2) 设置 HTTPS_PROXY 走代理\n"
        "  3) 手动下载后设置 PYSHADE_ESBUILD_PATH 指向二进制"
    ) from last_error


def ensure_esbuild() -> Path:
    """返回可执行的 esbuild 路径:env 覆盖 → 缓存命中 → 下载校验落位。"""
    override = os.environ.get('PYSHADE_ESBUILD_PATH')
    if override:
        path = Path(override)
        if not path.is_file():
            raise EsbuildAcquireError(f"PYSHADE_ESBUILD_PATH 指向的文件不存在: {path}")
        return path

    plat = esbuild_platform()
    target = cache_root() / 'esbuild' / ESBUILD_VERSION / _binary_name(plat)
    if target.is_file():
        return target

    registry = os.environ.get('PYSHADE_NPM_REGISTRY', DEFAULT_REGISTRY).rstrip('/')
    url = f'{registry}/@esbuild/{plat}/-/{plat}-{ESBUILD_VERSION}.tgz'
    l.info("pyshade.bundler: 下载 esbuild {} ({})", ESBUILD_VERSION, url)
    blob = _download(url)

    binary = _extract_binary(blob, _binary_member(plat))
    expected = _BINARY_SHA256.get(plat, '')
    actual = hashlib.sha256(binary).hexdigest()
    if expected and actual != expected:
        raise EsbuildAcquireError(
            f"esbuild 二进制校验失败(platform={plat}):期望 {expected},实际 {actual};"
            "镜像内容可能被篡改,请改用官方源或核对 PYSHADE_NPM_REGISTRY"
        )
    if not expected:
        l.warning("pyshade.bundler: 平台 {} 无 pin 校验值,跳过校验(sha256={})", plat, actual)

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
        tmp.write(binary)
        tmp_path = Path(tmp.name)
    tmp_path.chmod(tmp_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.replace(tmp_path, target)
    return target


def _extract_binary(tarball: bytes, member: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        tar_path = Path(tmp) / 'esbuild.tgz'
        tar_path.write_bytes(tarball)
        try:
            with tarfile.open(tar_path, 'r:gz') as tar:
                extracted = tar.extractfile(member)
                if extracted is None:
                    raise EsbuildAcquireError(f"tarball 内找不到 {member}")
                return extracted.read()
        except tarfile.TarError as exc:
            raise EsbuildAcquireError(f"tarball 解析失败: {exc}") from exc


def run_esbuild(
    esbuild: Path,
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> None:
    result = subprocess.run(
        [str(esbuild), *args],
        capture_output=True,
        encoding='utf-8',
        errors='replace',
        cwd=cwd,
        env=env,
        timeout=600,
    )
    stderr = (result.stderr or '').strip()
    if result.returncode != 0:
        raise RuntimeError(f"esbuild 失败(exit {result.returncode}):\n{stderr[-4000:]}")
    if stderr:
        l.debug("esbuild: {}", stderr)
