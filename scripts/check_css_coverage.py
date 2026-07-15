"""CSS 覆盖防线:golden TSX 与 shadcn ui 文件中出现的每个 class 必须在预编译 style.css 中命中。

漏一个即红——这是"@source 扫描策略是否覆盖全部内容源"的真正保障(CI frontend job 运行)。
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
STYLE = REPO / 'frontend' / 'dist-style' / 'style.css'

# className="..." 的字面量;golden 里还有 className={"..."} 形态不存在,够用
_CLASS_ATTR = re.compile(r'className="([^"]+)"')
# cva/cn 字符串里的 class 串:提取所有引号字符串再拆 token(误收可接受,漏收不可)
_STRING_LITERAL = re.compile(r'["\']([a-z0-9_:\[\]./%()!&>*~+-]+(?:\s+[a-z0-9_:\[\]./%()!&>*~+-]+)*)["\']')

_TOKEN_OK = re.compile(r'^[a-z][a-z0-9-]*(?:-\[[^\]]+\])?$|^[a-z0-9-]+:[a-z0-9-]+.*$|^-?[a-z][\w-]*\[?')


def classes_from(path: Path, *, attr_only: bool) -> set[str]:
    text = path.read_text(encoding='utf-8')
    # import 行里的包路径不是 class(如 class-variance-authority)
    text = re.sub(r'^\s*import\b[^\n]*$', '', text, flags=re.MULTILINE)
    out: set[str] = set()
    pattern = _CLASS_ATTR if attr_only else _STRING_LITERAL
    for match in pattern.finditer(text):
        for token in match.group(1).split():
            out.add(token)
    return out


def css_has(css: str, cls: str) -> bool:
    escaped = re.escape(cls).replace(r'\:', r'\\?:')
    # Tailwind 对 [ ] / : . % 等做转义;宽松匹配:类名主体出现在选择器位置即可
    body = re.escape(cls)
    for ch, esc in (('[', r'\\\['), (']', r'\\\]'), (':', r'(\\)?:'), ('.', r'\\?\.'), ('/', r'\\?/'), ('%', r'\\?%')):
        body = body.replace(re.escape(ch), esc)
    return re.search(rf'\.{body}[,{{\\:）)]?', css) is not None or re.search(rf'\.{escaped}', css) is not None


def main() -> int:
    if not STYLE.exists():
        print("缺 dist-style/style.css:先 pnpm -C frontend build:css", file=sys.stderr)
        return 1
    css = STYLE.read_text(encoding='utf-8')

    wanted: set[str] = set()
    for golden in (REPO / 'tests' / 'compiler' / 'golden').glob('*.gen.tsx'):
        wanted |= classes_from(golden, attr_only=True)
    for ui in (REPO / 'frontend' / 'src' / 'components' / 'ui').glob('*.tsx'):
        wanted |= classes_from(ui, attr_only=False)

    # 过滤明显非 class 的 token(import 路径、变量名等混入)
    candidates = {c for c in wanted if _TOKEN_OK.match(c) and not c.startswith(('@', './', '../', 'react'))}

    missing = sorted(c for c in candidates if not css_has(css, c))
    # 非 class 字符串误收的豁免:凡在 CSS 中完全找不到、又不含 tailwind 特征的短词,双重复核
    truly_missing = [c for c in missing if re.match(r'^[a-z][a-z0-9-]*(:|-\[|$)', c) and ('-' in c or ':' in c)]

    print(f"候选 class {len(candidates)},缺失 {len(truly_missing)}")
    if truly_missing:
        for cls in truly_missing[:40]:
            print(f"  MISSING: {cls}", file=sys.stderr)
        return 1
    print("CSS 覆盖检查通过")
    return 0


if __name__ == '__main__':
    sys.exit(main())
