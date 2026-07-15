"""standalone 打包链(design.md §3.12,M3):pyshade init / pyshade package 的编排层。

用户环境 = Python + Rust(零 Node):便携 CPython(python-build-standalone,下载缓存)
+ `pyshade bundle` 前端产物烤入二进制 + cargo-tauri 出安装包。
Phase 3 补 package_app 编排入口;当前先落获取链与脚手架。
"""

from pyshade.packager._cpython import (
    CPYTHON_VERSION,
    PBS_RELEASE,
    CpythonAcquireError,
    cpython_triple,
    ensure_cpython_tarball,
    extract_pyembed,
    pyembed_python_path,
    pyembed_stamp,
    read_pyembed_stamp,
)

__all__ = [
    'CPYTHON_VERSION',
    'PBS_RELEASE',
    'CpythonAcquireError',
    'cpython_triple',
    'ensure_cpython_tarball',
    'extract_pyembed',
    'pyembed_python_path',
    'pyembed_stamp',
    'read_pyembed_stamp',
]
