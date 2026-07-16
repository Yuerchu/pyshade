"""build.py 的输出目录定向清理:旧组件的 md 快照不残留,用户手放的文件不误删。"""

import importlib.util
import sys
from pathlib import Path

_BUILD_PY = Path(__file__).resolve().parents[2] / 'docs_site' / 'build.py'
_spec = importlib.util.spec_from_file_location('docs_site_build', _BUILD_PY)
assert _spec is not None and _spec.loader is not None
_build = importlib.util.module_from_spec(_spec)
sys.modules.setdefault('docs_site_build', _build)
_spec.loader.exec_module(_build)


class TestCleanOutputs:
    def test_stale_products_removed_user_files_kept(self, tmp_path: Path) -> None:
        (tmp_path / 'en' / 'md' / 'components').mkdir(parents=True)
        (tmp_path / 'en' / 'md' / 'components' / 'OldComponent.md').write_text('stale', encoding='utf-8')
        (tmp_path / 'llms.txt').write_text('stale', encoding='utf-8')
        (tmp_path / 'index.html').write_text('stale', encoding='utf-8')
        (tmp_path / 'CNAME').write_text('docs.example.com', encoding='utf-8')
        (tmp_path / '_headers').mkdir()

        _build.clean_outputs(tmp_path)

        assert not (tmp_path / 'en').exists()  # 已知产物子路径被清
        assert not (tmp_path / 'llms.txt').exists()
        assert not (tmp_path / 'index.html').exists()
        assert (tmp_path / 'CNAME').exists()  # 用户手放的文件幸存
        assert (tmp_path / '_headers').is_dir()
