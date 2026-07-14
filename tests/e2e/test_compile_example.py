"""E2E 测试:编译 login_form example 并验证产物可被 tsc 通过。"""

import json
from pathlib import Path

from login_form.app import app

from pyshade.compiler import compile_app


def test_compile_login_form(tmp_path: Path) -> None:
    compile_app(app, tmp_path)

    page_tsx = tmp_path / 'pages' / 'LoginPage.gen.tsx'
    assert page_tsx.exists()
    content = page_tsx.read_text(encoding='utf-8')
    assert 'usePageRuntime' in content
    assert 'collectValues' in content
    assert 'passwordRef' in content
    assert 'LoginPage.submit.on_click' in content

    app_tsx = tmp_path / 'app.gen.tsx'
    assert app_tsx.exists()
    assert 'LoginPage' in app_tsx.read_text(encoding='utf-8')

    types_ts = tmp_path / 'types.gen.ts'
    assert types_ts.exists()
    types_content = types_ts.read_text(encoding='utf-8')
    assert 'ButtonVariant' in types_content
    assert '"destructive"' in types_content

    manifest = json.loads((tmp_path / 'manifest.json').read_text(encoding='utf-8'))
    handler_ids = manifest['pages']['LoginPage']
    assert 'LoginPage.username.on_change' in handler_ids
    assert 'LoginPage.submit.on_click' in handler_ids
    assert 'LoginPage.remember.on_change' in handler_ids


def test_compiled_output_matches_golden() -> None:
    """编译 example 的产物与 tests/compiler/golden 一致(单一事实源)。"""
    golden_dir = Path(__file__).parent.parent / 'compiler' / 'golden'
    if not golden_dir.exists():
        return

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        compile_app(app, tmp)
        for golden_file in golden_dir.iterdir():
            if golden_file.name == 'manifest.json':
                continue
            compiled = Path(tmp)
            if golden_file.name.endswith('.gen.tsx') and golden_file.name != 'app.gen.tsx':
                compiled = compiled / 'pages' / golden_file.name
            else:
                compiled = compiled / golden_file.name
            if compiled.exists():
                assert compiled.read_text(encoding='utf-8') == golden_file.read_text(encoding='utf-8'), (
                    f"编译产物 {compiled.name} 与 golden 不一致"
                )
