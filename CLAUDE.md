# PyShade

用 Python 构建现代桌面应用的框架:Pydantic 组件 DTO 编译成 shadcn/ui React,跑在系统 WebView(pytauri 壳)。

**`docs/design.md` 是架构单一事实源**,改动架构决策必须同步该文档。M0(端到端可行性)、
M1(表达式系统与编译期校验)、M2(组件铺量/零 Node 打包/路由/Each)已完成,当前迈向 M3(打包分发链)。

## 关键决策速览(详见 design.md)

- 编译路线(非运行时协议):Python DTO → React 代码生成,编译期暴露错误
- 所有权公理(§3.3):每个 prop 恰一个所有者——普通值=服务端(rt.ov)、`Expr[T]`=客户端(内联 JS,
  boundProps 防御)、`ServerRef[T]`=ServerState 字段(`$s:` 命名空间,auto-diff/推送)、
  Each 模板内普通值=构建期常量(`.$t[` anchor 不可 Update)
- 表达式子集(§3.4):`&`/`|`/`~` + 比较 + `+`,构造期定型,`__bool__` 抛错,双端求值(to_js/evaluate)
- 多页面路由(§3.11):route 归客户端(`navigate`→`rt.navigate`,零 IPC);服务端 `Navigate` 编码为
  `$nav` 保留地址 patch;overrides/push 提升 App 级共享 store,页面状态 unmount 即丢
- 零 Node 打包(§3.6):`pyshade bundle` = esbuild pin 二进制(裸下载缓存)+ wheel 内物化 vendor
  (NODE_PATH)+ CSS 发版预编译(双层变量保运行时主题);entry.tsx 从 IR 收集,非 import 静态分析
- 壳层 pytauri(锁 minor 版本,pre-1.0 有 breaking):PyO3 进程内嵌入,无 TCP 端口
- ASGI over IPC 适配器自建:自定义 `invoke_handler` → ASGI scope → FastAPI,流式走 Tauri Channel
  (PSA1 封包);SSE 推送复用同一流式分支,零新协议;shutdown 必须取消 in-flight 请求(SSE 挂死教训)
- 打包:python-build-standalone + Tauri bundler(不用 PyInstaller/Nuitka)

## 工具链

- Python:uv(3.10-3.13,src layout),`uv run pytest` / `uv run ruff check` / `uv run pyright`
  (strict + reportUnnecessaryTypeIgnoreComment:测试锚定应报错用法,ignore 双向锁定)
- 前端(`frontend/`):pnpm,React + shadcn/ui + Tailwind;`pnpm -C frontend build` 前需先
  `uv run pyshade build login_form.app:app --out frontend/src/generated`(PYTHONPATH=examples/login_form/src)
- 模块边界(依赖单向,`expr.py`/`state.py`/`nav.py` 是叶子):
  `expr.py`(表达式树 + ClientVal/ItemRef + value_of)、`state.py`(ServerState/ServerRef/patch sink)、
  `nav.py`(navigate/Navigate,运行时零依赖)、`components/`(DTO,依赖 expr/state/nav;
  `each.py` 的 render-prop 模板)、`page.py`(布局 + ClientVal 收集 + `$t` 模板 anchor)、
  `events.py`(Update 所有权拒绝 + item_index)、`compiler/`(ir 的 binding 四分类 → emit_page →
  checks 的 G 规则 + check_app)、`push.py`(PatchBus + SSE)、`asgi/`(IPC 适配)、
  `bundler/`(零 Node 管线:esbuild/staging/entry/assets)、`testing/`(真机 E2E harness)、`cli.py`
- 前端 runtime 边界:`patches.ts`(mergePatches + `$nav` 保留地址)、`store.ts`(App 级共享 store
  context)、`app.tsx`(ShadeAppProvider/ShadeRouter,push 订阅提升 App 层)、`page.ts`
  (usePageRuntime 双模式:有 Provider 走共享 store,无则页面本地)
- golden 测试:`PYSHADE_UPDATE_GOLDEN=1 uv run pytest tests/compiler` 再看 git diff 确认改动范围
- 真机 E2E:`uv run pytest tests/e2e_native -m e2e_native`(需 pnpm build + build:testkit 产物;CI windows job 自动跑)
- 本地有 pytauri 源码可查:`~/Documents/Code/pytauri`
