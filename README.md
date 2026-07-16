# PyShade

[![CI](https://github.com/Yuerchu/pyshade/actions/workflows/ci.yml/badge.svg)](https://github.com/Yuerchu/pyshade/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pyshade)](https://pypi.org/project/pyshade/)
[![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)](https://pypi.org/project/pyshade/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Build modern desktop apps in **pure Python** — Pydantic component DTOs compiled to
[shadcn/ui](https://ui.shadcn.com/) React, running on the system WebView via
[pytauri](https://github.com/pytauri/pytauri).

- **No bundled Chromium, no TCP port, no Node.js** on your machine — ever.
- **Compile-time errors.** Pages are plain Python classes; invalid props, dead references
  and type mismatches fail your build, not your users.
- **Explicit ownership.** Every prop has exactly one owner: server value, client expression,
  controlled `ClientVal`, `ServerState` field, or build-time constant.
- **One command to ship.** `pyshade init` + `pyshade package` produce a standalone installer
  (NSIS / DMG / DEB) with an embedded CPython — ~27 MB on Windows.

## Requirements

Python 3.10–3.13 on Windows, macOS or Linux.

## Install

```bash
pip install "pyshade[native]"
```

The `native` extra pulls in `pytauri-wheel`, so the native window works without a Rust
toolchain. Add `pyshade[content]` for the compile-time Markdown/CodeBlock components.

## Quickstart

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

```bash
pyshade dev hello.app:app     # browser dev loop: edit -> auto reload
pyshade serve hello.app:app   # production web serving (single process)
```

For a native window, add a ten-line `__main__.py` calling `pyshade.shell.run(app, ...)` —
see [docs/packaging.md](docs/packaging.md) and the [examples](examples/).

## Ship an installer

```bash
pyshade init                     # scaffold src-tauri once (Rust toolchain required)
pyshade package hello.app:app    # portable CPython + baked frontend -> platform installer
```

## Documentation

- **Docs site** (dogfooded — it is itself a PyShade app): <https://pyshade-docs.pages.dev>
  (en/zh, live demos, per-component props tables, `llms.txt`)
- Design document (zh-CN, single source of truth): [docs/design.md](docs/design.md)
- Packaging guide: [docs/packaging.md](docs/packaging.md)

## Status

**Alpha.** Milestones M0–M4 are complete: compile pipeline with ownership checks,
client expressions, ServerState auto-diff + SSE push, 27 components, multi-page routing
with deep links and keep-alive, dark mode, zero-Node bundling, standalone installers
(three platforms, CI-verified), `pyshade dev` / `pyshade serve`, and this documentation
site. Expect breaking changes before 1.0.

## License

[MIT](LICENSE) © 2026 于小丘 Yuerchu
