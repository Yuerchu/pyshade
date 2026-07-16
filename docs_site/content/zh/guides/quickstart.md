## 安装

```bash
pip install "pyshade[native]"
```

`native` 附带 `pytauri-wheel`,原生窗口开箱即用、无需 Rust 工具链。
Python 3.10–3.13,Windows / macOS / Linux。

## 第一个应用

```python
# src/hello/app.py
from pyshade.app import ShadeApp
from pyshade.components import Button, Card, Input, Text
from pyshade.events import EventContext, Update
from pyshade.page import Page


def on_greet(ctx: EventContext) -> list[Update]:
    name = ctx.values.get('name', '') or 'world'
    return [Update(HelloPage.greeting, text=f'Hello, {name}!')]


class HelloPage(Page):
    name = Input(label='名字', placeholder='你的名字')
    greet = Button('打招呼', submit=True, on_click=on_greet)
    greeting = Text('', muted=True)

    card = Card(name, greet, greeting, title='Hello PyShade')


app = ShadeApp(title='Hello', pages=[HelloPage])
```

## 跑起来

```bash
pyshade dev hello.app:app     # 浏览器 dev loop:改代码 → 自动刷新
pyshade serve hello.app:app   # 生产 web 伺服(单进程)
```

要开原生窗口,再写一个十行的 `__main__.py` 调 `pyshade.shell.run(app, ...)`——
见仓库里的打包指南。

## 出安装包

```bash
pyshade init        # 一次性生成 src-tauri
pyshade package hello.app:app
```

它会下载便携 CPython、把前端 bundle 烤进二进制,产出平台安装包。
零 Node,不用手写 Rust。
