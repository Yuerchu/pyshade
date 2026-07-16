"""文档站全站组装:双 locale bundle(子进程)+ mock 注入 + llms.txt / md 快照 + 根跳转。

产物布局(--out,默认 dist-docs/):

    index.html            根跳转(navigator.language → /en/ 或 /zh/)
    en/  zh/              两次 pyshade bundle 三件套 + demo-mock.js + md/ 快照 + llms.txt
    llms.txt  llms-full.txt   en 版提升到根(llmstxt.org 约定位置)

双 locale 用子进程跑 bundle:同进程二次构造动态 Page/ServerState 会撞全局态。
用法:PYTHONPATH=docs_site/src python docs_site/build.py --out dist-docs [--base-url URL]
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from docs_site.export import inject_mock_script, llms_full_txt, llms_txt, md_snapshots, redirect_html
from docs_site.i18n import LOCALES, Locale

from pyshade.docs import collect_components

DOCS_SITE_DIR = Path(__file__).resolve().parent
DEFAULT_BASE_URL = 'https://pyshade-docs.pages.dev'


def _bundle_locale(locale: Locale, out_dir: Path, *, base_url: str, workdir: Path) -> None:
    env = {
        **os.environ,
        'PYSHADE_DOCS_LOCALE': locale,
        'PYSHADE_DOCS_BASE_URL': base_url,
        'PYTHONPATH': os.pathsep.join(filter(None, [str(DOCS_SITE_DIR / 'src'), os.environ.get('PYTHONPATH')])),
    }
    command = [
        sys.executable,
        '-m',
        'pyshade.cli',
        'bundle',
        'docs_site.app:app',
        '--out',
        str(out_dir),
        '--workdir',
        str(workdir),
    ]
    subprocess.run(command, check=True, env=env)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def build_site(out: Path, *, base_url: str, workdir: Path) -> None:
    docs = collect_components()
    out.mkdir(parents=True, exist_ok=True)

    for locale in LOCALES:
        locale_dir = out / locale
        _bundle_locale(locale, locale_dir, base_url=base_url, workdir=workdir / f'bundle-{locale}')

        # demo mock:静态站无 Python 后端,mock 先于 app.js 就位
        shutil.copy2(DOCS_SITE_DIR / 'assets' / 'demo-mock.js', locale_dir / 'demo-mock.js')
        index = locale_dir / 'index.html'
        _write(index, inject_mock_script(index.read_text(encoding='utf-8')))

        for rel_path, text in md_snapshots(docs, locale).items():
            _write(locale_dir / rel_path, text)
        _write(locale_dir / 'llms.txt', llms_txt(docs, base_url=base_url, locale=locale))
        _write(locale_dir / 'llms-full.txt', llms_full_txt(docs, locale))

    # en 版 llms 提升到根(llmstxt.org 约定位置)+ 根跳转
    shutil.copy2(out / 'en' / 'llms.txt', out / 'llms.txt')
    shutil.copy2(out / 'en' / 'llms-full.txt', out / 'llms-full.txt')
    _write(out / 'index.html', redirect_html())


def main() -> int:
    parser = argparse.ArgumentParser(description='PyShade 文档站全站组装')
    parser.add_argument('--out', default='dist-docs', help='输出目录')
    parser.add_argument('--base-url', default=os.environ.get('PYSHADE_DOCS_BASE_URL', DEFAULT_BASE_URL))
    parser.add_argument('--workdir', default='.pyshade/docs-site', help='bundle 工作目录')
    args = parser.parse_args()

    out = Path(args.out).absolute()
    build_site(out, base_url=args.base_url, workdir=Path(args.workdir).absolute())
    print(f'文档站就绪 → {out}(locales: {", ".join(LOCALES)};llms.txt + md 快照已挂)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
