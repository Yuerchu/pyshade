# PyShade

用 Python 构建现代桌面应用的框架:Pydantic 组件 DTO 编译成 shadcn/ui React,跑在系统 WebView(pytauri 壳)。

**`docs/design.md` 是架构单一事实源**,改动架构决策必须同步该文档。当前处于里程碑 M0(端到端可行性验证)。

## 关键决策速览(详见 design.md)

- 编译路线(非运行时协议):Python DTO → React 代码生成,编译期暴露错误
- 双状态模型:`ClientState`(可编译表达式子集,SQLAlchemy 式运算符重载)/ `ServerState`(任意 Python,IPC 回传)
- 壳层 pytauri(锁 minor 版本,pre-1.0 有 breaking):PyO3 进程内嵌入,无 TCP 端口
- ASGI over IPC 适配器自建:自定义 `invoke_handler` → ASGI scope → FastAPI,流式走 Tauri Channel
- 打包:python-build-standalone + Tauri bundler(不用 PyInstaller/Nuitka)

## 工具链

- Python:uv(3.10+,src layout),`uv run pytest` / `uv run ruff check` / `uv run pyright`
- 前端(`frontend/`):pnpm,React + shadcn/ui + Tailwind,esbuild 做按需打包
- 模块边界:`components/`(DTO)、`state.py`、`expr.py`(表达式树)、`compiler/`(代码生成)、
  `asgi/`(IPC 适配)、`cli.py`
- 本地有 pytauri 源码可查:`~/Documents/Code/pytauri`
