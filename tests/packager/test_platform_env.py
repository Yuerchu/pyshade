"""平台修补与构建环境:RUSTFLAGS 三平台精确锚定、PYO3_PYTHON、追加不覆盖。"""

from pathlib import Path

from pyshade.packager._platform import build_env, rustflags_for

_LIB = Path('/proj/src-tauri/pyembed/python/lib')


class TestRustflags:
    def test_windows_none(self) -> None:
        assert rustflags_for('windows', product_name='my-app', pyembed_lib=_LIB) is None

    def test_darwin(self) -> None:
        flags = rustflags_for('darwin', product_name='my-app', pyembed_lib=_LIB)
        assert flags == f'-C link-arg=-Wl,-rpath,@executable_path/../Resources/lib -L {_LIB}'

    def test_linux_with_appimage_fallback_rpath(self) -> None:
        flags = rustflags_for('linux', product_name='my-app', pyembed_lib=_LIB)
        assert flags is not None
        assert flags == (
            f'-C link-arg=-Wl,-rpath,$ORIGIN/../lib/my-app/lib -C link-arg=-Wl,-rpath,$ORIGIN/../lib -L {_LIB}'
        )
        assert '$ORIGIN' in flags  # 字面量透传,不做 shell 展开


class TestBuildEnv:
    def test_pyo3_python_absolute(self) -> None:
        python = Path('/proj/src-tauri/pyembed/python/bin/python3')
        env = build_env(
            {'PATH': '/usr/bin'},
            system='linux',
            pyembed_python=python,
            pyembed_dir=Path('/proj/src-tauri/pyembed'),
            product_name='my-app',
        )
        assert env['PYO3_PYTHON'] == str(python)
        assert env['PATH'] == '/usr/bin'
        assert '$ORIGIN/../lib/my-app/lib' in env['RUSTFLAGS']

    def test_rustflags_appended_not_replaced(self) -> None:
        env = build_env(
            {'RUSTFLAGS': '-C debuginfo=0'},
            system='darwin',
            pyembed_python=Path('/p/python3'),
            pyembed_dir=Path('/p'),
            product_name='x',
        )
        assert env['RUSTFLAGS'].startswith('-C debuginfo=0 ')
        assert '@executable_path/../Resources/lib' in env['RUSTFLAGS']

    def test_windows_has_no_rustflags_key(self) -> None:
        env = build_env(
            {},
            system='windows',
            pyembed_python=Path('C:/p/python.exe'),
            pyembed_dir=Path('C:/p'),
            product_name='x',
        )
        assert 'RUSTFLAGS' not in env
