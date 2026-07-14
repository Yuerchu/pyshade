"""页面定义:LoginPage(M0 六组件演示)。"""

from login_form import handlers
from pyshade.components import Button, ButtonVariant, Card, Input, PasswordInput, Switch, Text
from pyshade.page import Page


class LoginPage(Page):
    heading = Text('欢迎回来')
    username = Input(label='用户名', placeholder='请输入用户名', on_change=handlers.on_username_change)
    password = PasswordInput(label='密码', placeholder='请输入密码')
    remember = Switch(label='记住我', on_change=handlers.on_remember_change)
    submit = Button('登录', variant=ButtonVariant.DEFAULT, submit=True, on_click=handlers.on_submit)
    greeting = Text('', muted=True)

    card = Card(
        heading,
        username,
        password,
        remember,
        submit,
        greeting,
        title='登录',
        description='PyShade M0 演示',
    )
