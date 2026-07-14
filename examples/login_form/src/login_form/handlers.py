"""事件处理器:模块级具名函数,由 EventRegistry 收集。"""

from pyshade.events import EventContext, Update


def on_username_change(ctx: EventContext) -> None:
    print(f'username committed: {ctx.value!r}')


def on_remember_change(ctx: EventContext) -> None:
    print(f'remember toggled: {ctx.value!r}')


def on_submit(ctx: EventContext) -> list[Update]:
    from login_form.pages import LoginPage

    name = str(ctx.values.get('username', ''))
    password = str(ctx.values.get('password', ''))
    if not name or not password:
        return [Update(LoginPage.greeting, text='用户名和密码不能为空')]
    return [Update(LoginPage.greeting, text=f'你好,{name}!(密码长度 {len(password)})')]


def bench_echo(ctx: EventContext) -> None:
    pass
