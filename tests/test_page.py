import pytest

from pyshade.components import Button, Card, Input, PasswordInput, Switch, Text
from pyshade.page import LayoutError, Page, anchor_of, iter_nodes


def _noop(ctx: object) -> None: ...


class TestLayoutCollection:
    def test_login_page_shape(self) -> None:
        class LoginPage(Page):
            heading = Text('欢迎回来')
            username = Input(label='用户名', on_change=_noop)
            password = PasswordInput(label='密码')
            remember = Switch(label='记住我')
            submit = Button('登录', submit=True, on_click=_noop)
            greeting = Text('', muted=True)

            card = Card(heading, username, password, remember, submit, greeting, title='登录')

        assert LoginPage.__shade_roots__ == [LoginPage.card]
        assert anchor_of(LoginPage.username) == 'LoginPage.username'
        assert anchor_of(LoginPage.card) == 'LoginPage.card'
        assert set(LoginPage.__shade_anchors__) == {
            'LoginPage.heading',
            'LoginPage.username',
            'LoginPage.password',
            'LoginPage.remember',
            'LoginPage.submit',
            'LoginPage.greeting',
            'LoginPage.card',
        }

    def test_multiple_roots_keep_declaration_order(self) -> None:
        class TwoRoots(Page):
            first = Text('a')
            second = Text('b')

        assert TwoRoots.__shade_roots__ == [TwoRoots.first, TwoRoots.second]

    def test_iter_nodes_preorder(self) -> None:
        class P(Page):
            leaf = Text('leaf')
            inner = Card(leaf, title='inner')
            outer = Card(inner)
            tail = Text('tail')

        names = [anchor_of(node) for node in iter_nodes(P)]
        assert names == ['P.outer', 'P.inner', 'P.leaf', 'P.tail']


class TestAnonymousComponents:
    def test_anonymous_anchor_paths(self) -> None:
        class P(Page):
            card = Card(Text('a'), Text('b'))

        anchors = set(P.__shade_anchors__)
        assert 'P.card[0]' in anchors
        assert 'P.card[1]' in anchors

    def test_nested_anonymous_paths(self) -> None:
        class P(Page):
            card = Card(Card(Text('deep')))

        assert 'P.card[0]' in P.__shade_anchors__
        assert 'P.card[0][0]' in P.__shade_anchors__

    def test_anonymous_with_event_warns(self) -> None:
        with pytest.warns(UserWarning, match='handlerId'):

            class P(Page):
                card = Card(Button('anon', on_click=_noop))

    def test_anonymous_without_event_no_warning(self) -> None:
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter('error')

            class P(Page):
                card = Card(Text('static'))


class TestListFieldRejected:
    def test_component_list_field_rejected(self) -> None:
        with pytest.raises(LayoutError, match='Stack'):

            class ListFieldPage(Page):
                rows = [Text('a'), Text('b')]

    def test_component_tuple_field_rejected(self) -> None:
        with pytest.raises(LayoutError, match='Stack'):

            class TupleFieldPage(Page):
                rows = (Text('a'), Text('b'))


class TestLayoutErrors:
    def test_single_parent_conflict(self) -> None:
        with pytest.raises(LayoutError, match='一个父容器'):

            class P(Page):
                shared = Text('shared')
                left = Card(shared)
                right = Card(shared)

    def test_field_alias_rejected(self) -> None:
        shared = Text('x')
        with pytest.raises(LayoutError, match='同一实例'):

            class P(Page):
                first = shared
                second = shared

    def test_cross_page_reuse_rejected(self) -> None:
        shared = Text('x')

        class PageA(Page):
            item = shared

        with pytest.raises(LayoutError, match='跨页面'):

            class PageB(Page):
                item = shared

    def test_anonymous_reuse_rejected(self) -> None:
        anon = Text('anon')
        with pytest.raises(LayoutError, match='不可复用'):

            class P(Page):
                left = Card(anon)
                right = Card(anon)

    def test_anchor_of_unattached_component(self) -> None:
        with pytest.raises(LayoutError, match='Page'):
            anchor_of(Text('floating'))
