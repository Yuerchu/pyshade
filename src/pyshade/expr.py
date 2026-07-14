"""表达式系统(design.md §3.4)。

SQLAlchemy 式运算符重载构建表达式树,编译期翻译成 JS:
`&`/`|`/`~` 代替 and/or/not,`__bool__` 抛 TypeError,`ClientVal[T]` 泛型描述符。
"""
