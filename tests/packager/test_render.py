"""模板渲染:替换、残留检测。"""

import pytest

from pyshade.packager._render import RenderError, render


class TestRender:
    def test_replaces_all_params(self) -> None:
        out = render('name = "{{crate_name}}"\nlib = "{{lib_name}}"', {'crate_name': 'a-b', 'lib_name': 'a_b_lib'})
        assert out == 'name = "a-b"\nlib = "a_b_lib"'

    def test_leftover_placeholder_rejected(self) -> None:
        with pytest.raises(RenderError, match='未替换占位符'):
            render('x = {{missing}}', {'crate_name': 'a'})

    def test_unused_param_is_fine(self) -> None:
        assert render('static', {'unused': 'x'}) == 'static'
