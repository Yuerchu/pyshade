# PyShade

用 Python 构建现代桌面应用的框架:Pydantic 组件 DTO 编译成 shadcn/ui React,跑在系统 WebView(pytauri 壳)。

**`docs/design.md` 是架构单一事实源**,改动架构决策必须同步该文档。M0(端到端可行性)与
M1(表达式系统与编译期校验)已完成,当前迈向 M2(组件铺量与按需打包)。

## 关键决策速览(详见 design.md)

- 编译路线(非运行时协议):Python DTO → React 代码生成,编译期暴露错误
- 所有权公理(§3.3):每个 prop 恰一个所有者——普通值=服务端(rt.ov)、`Expr[T]`=客户端(内联 JS,
  boundProps 防御)、`ServerRef[T]`=ServerState 字段(`$s:` 命名空间,auto-diff/推送)
- 表达式子集(§3.4):`&`/`|`/`~` + 比较 + `+`,构造期定型,`__bool__` 抛错,双端求值(to_js/evaluate)
- 壳层 pytauri(锁 minor 版本,pre-1.0 有 breaking):PyO3 进程内嵌入,无 TCP 端口
- ASGI over IPC 适配器自建:自定义 `invoke_handler` → ASGI scope → FastAPI,流式走 Tauri Channel
  (PSA1 封包);SSE 推送复用同一流式分支,零新协议
- 打包:python-build-standalone + Tauri bundler(不用 PyInstaller/Nuitka)

## 工具链

- Python:uv(3.10-3.13,src layout),`uv run pytest` / `uv run ruff check` / `uv run pyright`
  (strict + reportUnnecessaryTypeIgnoreComment:测试锚定应报错用法,ignore 双向锁定)
- 前端(`frontend/`):pnpm,React + shadcn/ui + Tailwind;`pnpm -C frontend build` 前需先
  `uv run pyshade build login_form.app:app --out frontend/src/generated`(PYTHONPATH=examples/login_form/src)
- 模块边界(依赖单向,`expr.py`/`state.py` 是叶子):
  `expr.py`(表达式树 + ClientVal + value_of)、`state.py`(ServerState/ServerRef/patch sink)、
  `components/`(DTO,依赖 expr/state)、`page.py`(布局 + ClientVal 收集)、`events.py`(Update 所有权拒绝)、
  `compiler/`(ir 的 binding 四分类 → emit_page → checks 的 G 规则)、`push.py`(PatchBus + SSE)、
  `asgi/`(IPC 适配)、`testing/`(真机 E2E harness)、`cli.py`
- golden 测试:`PYSHADE_UPDATE_GOLDEN=1 uv run pytest tests/compiler` 再看 git diff 确认改动范围
- 真机 E2E:`uv run pytest tests/e2e_native -m e2e_native`(需 pnpm build + build:testkit 产物;CI windows job 自动跑)
- 本地有 pytauri 源码可查:`~/Documents/Code/pytauri`
