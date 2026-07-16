"""平台修补与构建环境:rustc flag token 列表、CARGO_ENCODED_RUSTFLAGS 合并语义、PYO3_PYTHON。

token 列表 + 0x1f 分隔(而非空格拼接 RUSTFLAGS):路径/productName 含空格时
cargo 的空白切分会拆断 flag(链接失败或 rpath 断裂)。
"""

from pathlib import Path

from pyshade.packager._platform import build_env, rustflags_for

_LIB = Path('/proj/src-tauri/pyembed/python/lib')


class TestRustflags:
    def test_windows_none(self) -> None:
        assert rustflags_for('windows', product_name='my-app', pyembed_lib=_LIB) is None

    def test_darwin(self) -> None:
        flags = rustflags_for('darwin', product_name='my-app', pyembed_lib=_LIB)
        assert flags == ['-C', 'link-arg=-Wl,-rpath,@executable_path/../Resources/lib', '-L', str(_LIB)]

    def test_linux_with_appimage_fallback_rpath(self) -> None:
        flags = rustflags_for('linux', product_name='my-app', pyembed_lib=_LIB)
        assert flags == [
            '-C',
            'link-arg=-Wl,-rpath,$ORIGIN/../lib/my-app/lib',
            '-C',
            'link-arg=-Wl,-rpath,$ORIGIN/../lib',
            '-L',
            str(_LIB),
        ]
        assert flags is not None and any('$ORIGIN' in token for token in flags)  # 字面量透传,不做 shell 展开

    def test_space_in_product_name_single_token(self) -> None:
        # "My App" 的 rpath 必须是单 token:RUSTFLAGS 空白切分会把它拆成 $ORIGIN/../lib/My
        flags = rustflags_for('linux', product_name='My App', pyembed_lib=_LIB)
        assert flags is not None
        assert 'link-arg=-Wl,-rpath,$ORIGIN/../lib/My App/lib' in flags


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
        assert 'link-arg=-Wl,-rpath,$ORIGIN/../lib/my-app/lib' in env['CARGO_ENCODED_RUSTFLAGS'].split('\x1f')

    def test_user_rustflags_folded_in(self) -> None:
        # 用户已设 RUSTFLAGS:按空白拆分折入 ENCODED(cargo 对 RUSTFLAGS 的原生解析语义,无损)
        env = build_env(
            {'RUSTFLAGS': '-C debuginfo=0'},
            system='darwin',
            pyembed_python=Path('/p/python3'),
            pyembed_dir=Path('/p'),
            product_name='x',
        )
        parts = env['CARGO_ENCODED_RUSTFLAGS'].split('\x1f')
        assert parts[:2] == ['-C', 'debuginfo=0']
        assert 'link-arg=-Wl,-rpath,@executable_path/../Resources/lib' in parts
        assert env['RUSTFLAGS'] == '-C debuginfo=0'  # 键保留不删(被 cargo 忽略)

    def test_user_encoded_rustflags_preserved(self) -> None:
        # 用户已设 CARGO_ENCODED_RUSTFLAGS(cargo 规则:它存在则 RUSTFLAGS 被忽略)
        env = build_env(
            {'CARGO_ENCODED_RUSTFLAGS': '-C\x1flink-arg=-Wl,-rpath,/opt/my libs', 'RUSTFLAGS': '-C ignored'},
            system='linux',
            pyembed_python=Path('/p/python3'),
            pyembed_dir=Path('/p'),
            product_name='x',
        )
        parts = env['CARGO_ENCODED_RUSTFLAGS'].split('\x1f')
        assert parts[:2] == ['-C', 'link-arg=-Wl,-rpath,/opt/my libs']  # 含空格的既有 token 保真
        assert '-C ignored' not in env['CARGO_ENCODED_RUSTFLAGS']

    def test_windows_has_no_rustflags_key(self) -> None:
        env = build_env(
            {},
            system='windows',
            pyembed_python=Path('C:/p/python.exe'),
            pyembed_dir=Path('C:/p'),
            product_name='x',
        )
        assert 'RUSTFLAGS' not in env
        assert 'CARGO_ENCODED_RUSTFLAGS' not in env
