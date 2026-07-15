"""M2 examples 编译冒烟:component_gallery(全组件)与 task_board(路由 + Each)。

真实 tsc 校验在 CI frontend job(编译进 frontend/src/generated-{gallery,board} 后 typecheck)。
"""

import json
from pathlib import Path

from component_gallery.app import app as gallery_app
from task_board.app import app as board_app

from pyshade.compiler import compile_app


def test_compile_component_gallery(tmp_path: Path) -> None:
    compile_app(gallery_app, tmp_path)
    manifest = json.loads((tmp_path / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['routes'] == {
        'initial': 'WidgetsPage',
        'pages': ['WidgetsPage', 'FormPage', 'OverlaysPage', 'StructurePage'],
    }
    types_ts = (tmp_path / 'types.gen.ts').read_text(encoding='utf-8')
    assert 'export interface ChangelogEntry {' in types_ts


def test_compile_task_board(tmp_path: Path) -> None:
    compile_app(board_app, tmp_path)
    board = (tmp_path / 'pages' / 'BoardPage.gen.tsx').read_text(encoding='utf-8')
    assert 'rt.navigate("StatsPage")' in board
    assert '.map((tasksItem: TaskItem, tasksIndex: number) => (' in board
    assert 'item_key: tasksItem.id' in board
    manifest = json.loads((tmp_path / 'manifest.json').read_text(encoding='utf-8'))
    assert 'BoardPage.tasks.$t[0][2].on_click' in manifest['pages']['BoardPage']
    app_tsx = (tmp_path / 'app.gen.tsx').read_text(encoding='utf-8')
    assert 'initial="BoardPage"' in app_tsx
    assert 'push' in app_tsx
