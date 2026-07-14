"""编译器(design.md §3.1、§3.6)。

Python DTO → React 代码生成;静态收集组件 import 生成 entry.tsx,交 esbuild 按需打包。
编译期校验:props 类型、组件嵌套合法性、事件签名、死引用。
"""
