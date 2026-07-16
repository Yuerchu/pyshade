## Install

```bash
pip install "pyshade[native]"
```

`native` pulls in `pytauri-wheel` so the native window works without a Rust toolchain.
Python 3.10–3.13, Windows / macOS / Linux.

## Your first app

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
    name = Input(label='Name', placeholder='Your name')
    greet = Button('Greet', submit=True, on_click=on_greet)
    greeting = Text('', muted=True)

    card = Card(name, greet, greeting, title='Hello PyShade')


app = ShadeApp(title='Hello', pages=[HelloPage])
```

## Run it

```bash
pyshade dev hello.app:app     # browser dev loop: edit -> auto reload
pyshade serve hello.app:app   # production web serving (single process)
```

For the native window, add a ten-line `__main__.py` calling `pyshade.shell.run(app, ...)` —
see the packaging guide in the repository.

## Ship it

```bash
pyshade init        # scaffold src-tauri once
pyshade package hello.app:app
```

That downloads a portable CPython, bakes your frontend bundle into the binary and emits a
platform installer. No Node, no manual Rust code.
