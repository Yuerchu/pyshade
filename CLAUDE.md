# PyShade

用 Python 构建现代桌面应用的框架:Pydantic 组件 DTO 编译成 shadcn/ui React,跑在系统 WebView(pytauri 壳)。

**`docs/design.md` 是架构单一事实源**,改动架构决策必须同步该文档。M0-M4 已完成
(M4 = 文档站 dogfooding + props 内省 + 内容组件 + dark mode + pyshade serve + PyPI 发布链);
发版待用户手工:PyPI/TestPyPI trusted publisher 登记、CF Pages secrets、首个 v* tag。

## 关键决策速览(详见 design.md)

- 编译路线(非运行时协议):Python DTO → React 代码生成,编译期暴露错误
- 所有权公理(§3.3):每个 prop 恰一个所有者——普通值=服务端(rt.ov)、`Expr[T]`=客户端(内联 JS,
  boundProps 防御)、`ServerRef[T]`=ServerState 字段(`$s:` 命名空间,auto-diff/推送)、
  Each 模板内普通值=构建期常量(`.$t[` anchor 不可 Update)、`_const_props` 声明=构建期常量
  ('const' binding,M4 内容组件的源 prop,Update 构造期拒绝)
- 表达式子集(§3.4):`&`/`|`/`~` + 比较 + `+`,构造期定型,`__bool__` 抛错,双端求值(to_js/evaluate)
- 多页面路由(§3.11):route 归客户端(`navigate`→`rt.navigate`,零 IPC);服务端 `Navigate` 编码为
  `$nav` 保留地址 patch;overrides/push 提升 App 级共享 store;页面状态默认 unmount 即丢,
  `keep_alive=True` 保活(display:none);`#/PageName` 深链(生成 App 恒开,runtime 默认关);
  color scheme 同族归客户端(M4):class 策略 + `set_color_scheme()/toggle_color_scheme()` 零 IPC
  action(ClientAction 基类)+ localStorage 显式选择,`Theme(dark=ThemeTokens(...))` 暗色 token
- 内容组件(§3.13,M4):Heading/Link/Markdown/CodeBlock/Stack(文档流布局容器);markdown/高亮在**编译期**渲染
  (mistune+pygments 挂 `pyshade[content]` extra,escape=True 拒 raw HTML);样式走
  @tailwindcss/typography prose(只进 CSS 预编译)+ `.shade-hl` 作用域化高亮 token
- standalone 打包(§3.12):`pyshade init`(src-tauri 模板)+ `pyshade package`(便携 CPython +
  cargo-tauri),打包机 = Python + Rust 零 Node;`pyshade.shell.run` 双形态 shim;
  `pyshade dev` = supervisor/worker 整代重启 + generation SSE 刷新(浏览器向,窗口不进 dev loop);
  theme 口子只暴露 CSS 变量层(§3.6,对账测试锚定 token)
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
- 模块边界(依赖单向,`expr.py`/`state.py`/`actions.py`/`nav.py`/`scheme.py` 是叶子):
  `expr.py`(表达式树 + ClientVal/ItemRef + value_of)、`state.py`(ServerState/ServerRef/patch sink)、
  `actions.py`(ClientAction 基类:零 IPC action 的误用防线 + is_instance schema)、
  `nav.py`(navigate/Navigate)、`scheme.py`(set/toggle_color_scheme)、`components/`
  (DTO,依赖 expr/state/actions;`each.py` 的 render-prop 模板)、`page.py`(布局 + ClientVal 收集 + `$t` 模板 anchor)、
  `events.py`(Update 所有权拒绝 + item_index)、`compiler/`(ir 的 binding 五分类 → emit_page →
  checks 的 G 规则 + check_app)、`push.py`(PatchBus + SSE)、`asgi/`(IPC 适配)、
  `bundler/`(零 Node 管线:esbuild/staging/entry/assets)、`packager/`(standalone 安装包:
  _cpython 获取链/_scaffold 模板/_platform 修补/_pyembed 装配/_tauri_cli,§3.12)、
  `shell.py`(运行时壳层 shim,standalone/wheel 双形态)、`docs/`(introspect:model_fields
  内省 → ComponentDoc/FieldDoc,与 EMITTERS 双向对账,§3.10)、`web/`(serve:生产 web
  dispatcher,dev 复用 + 叠 dev 路由;多客户端共享 ServerState)、`testing/`(真机 E2E
  harness)、`cli.py`(build/bundle/init/package/serve/dev)
- 前端 runtime 边界:`patches.ts`(mergePatches + `$nav` 保留地址)、`store.ts`(App 级共享 store
  context)、`app.tsx`(ShadeAppProvider/ShadeRouter,push 订阅提升 App 层)、`page.ts`
  (usePageRuntime 双模式:有 Provider 走共享 store,无则页面本地)、`scheme.ts`(配色纯函数:
  localStorage 读写 + resolveDark + class 应用,app/page 共用)
- golden 测试:`PYSHADE_UPDATE_GOLDEN=1 uv run pytest tests/compiler` 再看 git diff 确认改动范围
- 真机 E2E:`uv run pytest tests/e2e_native -m e2e_native`(需 pnpm build + build:testkit 产物;CI windows job 自动跑)
- 本地有 pytauri 源码可查:`~/Documents/Code/pytauri`
