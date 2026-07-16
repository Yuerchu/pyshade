"""应用入口:`PYSHADE_DOCS_LOCALE` 选 locale(en/zh),双 locale 由 build.py 分进程构建。

`pyshade dev docs_site.app:app` 本地预览(真 Python 后端);静态站 demo 由
assets/demo-mock.js 模拟(design.md §3.10)。
"""

import os
from typing import cast

from docs_site.i18n import LOCALES, Locale, t
from docs_site.pages import all_pages
from pyshade.app import ShadeApp


def make_app(locale: Locale) -> ShadeApp:
    return ShadeApp(title=t('site_title', locale), pages=all_pages(locale), keep_alive=True)


_env = os.environ.get('PYSHADE_DOCS_LOCALE', 'en')
if _env not in LOCALES:
    raise RuntimeError(f"PYSHADE_DOCS_LOCALE 必须是 {'/'.join(LOCALES)} 之一(收到 {_env!r})")

app = make_app(cast('Locale', _env))
