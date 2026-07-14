"""缩进感知的行发射器:输出恒 LF 的 TSX 源码。"""

import json


class TsxWriter:
    def __init__(self, indent_size: int = 2) -> None:
        self._lines: list[str] = []
        self._indent = 0
        self._indent_str = ' ' * indent_size

    def line(self, text: str = '') -> None:
        if text:
            self._lines.append(f'{self._indent_str * self._indent}{text}')
        else:
            self._lines.append('')

    def indent(self) -> None:
        self._indent += 1

    def dedent(self) -> None:
        self._indent = max(0, self._indent - 1)

    def block(self, opener: str, closer: str) -> '_BlockContext':
        return _BlockContext(self, opener, closer)

    def to_string(self) -> str:
        return '\n'.join(self._lines) + '\n'


class _BlockContext:
    def __init__(self, writer: TsxWriter, opener: str, closer: str) -> None:
        self._writer = writer
        self._opener = opener
        self._closer = closer

    def __enter__(self) -> TsxWriter:
        self._writer.line(self._opener)
        self._writer.indent()
        return self._writer

    def __exit__(self, *args: object) -> None:
        self._writer.dedent()
        self._writer.line(self._closer)


def js_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def js_bool(value: bool) -> str:
    return 'true' if value else 'false'


def js_value(value: object) -> str:
    from enum import Enum

    if isinstance(value, bool):
        return js_bool(value)
    if isinstance(value, str):
        return js_string(value)
    if isinstance(value, Enum):
        return js_string(value.value)
    if value is None:
        return 'null'
    return str(value)
