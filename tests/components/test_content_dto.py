"""M4 内容组件 DTO:tag/const 声明/href 校验/Update 构造期拒绝。"""

import pytest
from pydantic import ValidationError

from pyshade.components import Heading, Link
from pyshade.components.base import const_props_of
from pyshade.events import Update
from pyshade.page import Page


class TestContentDto:
    def test_shade_tags(self) -> None:
        assert Heading('t')._shade_tag == 'Heading'  # pyright: ignore[reportPrivateUsage]
        assert Link('t', 'https://example.com')._shade_tag == 'Link'  # pyright: ignore[reportPrivateUsage]

    def test_const_props_declared(self) -> None:
        assert const_props_of(Heading('t')) == frozenset({'level'})
        assert const_props_of(Link('t', 'https://example.com')) == frozenset({'text', 'href'})

    def test_heading_level_bounds(self) -> None:
        assert Heading('t').level == 2
        assert Heading('t', level=4).level == 4
        with pytest.raises(ValidationError):
            Heading('t', level=5)  # pyright: ignore[reportArgumentType]

    def test_link_href_schemes(self) -> None:
        assert Link('主页', 'https://example.com').href == 'https://example.com'
        assert Link('邮件', 'mailto:hi@example.com').href == 'mailto:hi@example.com'
        for bad in ('ftp://example.com', 'javascript:alert(1)', '/docs', 'example.com'):
            with pytest.raises(ValidationError, match='href 仅接受'):
                Link('坏链接', bad)

    def test_unknown_prop_rejected(self) -> None:
        with pytest.raises(TypeError):
            Heading('t', size=3)  # pyright: ignore[reportCallIssue]


class ContentDtoPage(Page):
    head = Heading('标题')
    home = Link('主页', 'https://example.com')


class TestUpdateConstRejection:
    def test_const_prop_update_rejected(self) -> None:
        with pytest.raises(ValueError, match='构建期常量'):
            Update(ContentDtoPage.home, href='https://evil.example.com')
        with pytest.raises(ValueError, match='构建期常量'):
            Update(ContentDtoPage.home, text='改名')
        with pytest.raises(ValueError, match='构建期常量'):
            Update(ContentDtoPage.head, level=3)

    def test_plain_prop_still_updatable(self) -> None:
        update = Update(ContentDtoPage.head, text='新标题')
        assert update.to_payload() == {'target': 'ContentDtoPage.head', 'props': {'text': '新标题'}}
