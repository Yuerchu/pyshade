## 为什么是 PyShade

PyShade 把 **Pydantic 组件 DTO 编译成 shadcn/ui React**,跑在系统 WebView 上——
不捆绑 Chromium、不开 TCP 端口、你的机器上不需要 Node。

- **错误在编译期暴露。** 页面就是普通 Python 类;非法 props、死引用、类型不匹配在构建时报错,
  而不是在用户面前崩掉。
- **所有权显式。** 每个 prop 恰有一个所有者:服务端普通值、客户端表达式、受控 `ClientVal`、
  `ServerState` 字段,或构建期常量。
- **一条命令出安装包。** `pyshade init` + `pyshade package` 产出内嵌 CPython 的独立安装包
  (NSIS / DMG / DEB),Windows 下约 27 MB。

## 这个站怎么来的

本文档站本身就是一个 PyShade 应用。下面每个组件页都由框架自身的 Pydantic 模型编译而来,
每个在线演示都是真实生成代码。服务端 demo 在这个静态站上由 JavaScript 模拟——
本地跑 `pyshade dev docs_site.app:app` 才是真 Python 后端。

## 下一步

用上方按钮:**快速开始** 写第一个应用,**组件** 看全量参考(在线演示 + props 表)。
