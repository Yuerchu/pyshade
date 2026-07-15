# PyShade 设计文档

- 状态:草案 v0.2(2026-07-14,pytauri 评估完成并回填)
- 作者:于小丘 Yuerchu <admin@yuxiaoqiu.cn>
- 许可证:MIT
- 包名:`pyshade`(PyPI 已确认未占用;`shade` 被 OpenStack 遗留库占用,不使用)

## 1. 愿景

让 Python 开发者只写 Python,构建体积小、界面现代的跨平台桌面应用。

一句话定位:**Python DTO 编译成 shadcn/ui React 界面,跑在系统 WebView 里,业务逻辑留在 Python。**

## 2. 动机与竞品

| 方案 | 问题 |
|------|------|
| NiceGUI | Quasar 卡在 Material Design 2,审美过气;运行时协议路线,断连即瘫痪;所有交互(含密码输入)经 WebSocket 回传服务端;深度定制 UI 时抽象层漏 |
| Electron | 打包完整 Chromium,体积与内存开销大 |
| Tauri | 理念正确(系统 WebView + 小体积),但要求写 Rust,对 Python 开发者门槛高 |
| Reflex | 编译路线的先例,但 web 优先;事件处理器仍回传后端;编译慢是长期痛点 |
| Flet | 运行时协议路线的先例(Python + Flutter),协议设计成熟,可参考但路线不同 |

PyShade 的差异化组合:shadcn 审美(AI 时代事实标准)+ 编译期检查(Pydantic + 类型系统)+
系统 WebView 小体积 + 业务逻辑纯 Python。

## 3. 核心架构决策

### 3.1 编译路线,而非运行时协议

Python 侧的组件 DTO 在构建期编译成真实 React 代码,而不是运行时序列化组件树给预置 renderer 解释。

理由:

- 编译失败即暴露代码问题——props 类型错误、组件嵌套不合法、事件签名不匹配、死引用,全部在构建期报错,
  而不是运行时静默出错。
- 产物是真实 React 项目,可以按标准前端工具链做 tree-shaking 和优化。

技术背景:React + shadcn 没有运行时模板编译器(不同于 Vue/Quasar),JSX 必须预编译,shadcn 又是源码分发,
编译路线是与其模型自洽的选择。

### 3.2 逻辑分层:编译与"逻辑在哪跑"是两个独立的轴

Reflex 的教训:编译只覆盖结构层,不自动决定逻辑归属。PyShade 的划分:

- **UI 结构 + 纯交互派生态** → 编译进前端,运行时不碰 Python(开关联动 disable/hide、tab 切换、表单中间态)。
- **业务逻辑** → 留在 Python,经 IPC 回传执行。
- 不做任意 Python → JS 编译(Transcrypt/Pyodide 路线不碰)。

### 3.3 双状态模型:ClientState / ServerState

在类型层面把两个世界分开,开发者一眼知道自己写的代码在哪跑:

- `ClientState`:可编译。只接受受限表达式子集(运算符重载),编译成前端 JS。越界写法(在表达式里调任意函数、
  写 `if` 语句)编译期直接报错。
- `ServerState`:任意 Python,走 IPC 回传,由 FastAPI 应用层处理。

**所有权公理(M1 已实现)**:每个组件 prop 恰好有一个所有者,绑定形态即所有权,不存在优先级仲裁:

| prop 值 | 所有者 | 编译产物 | patch 可达性 |
|---|---|---|---|
| 普通 Python 值 | 服务端 | `rt.ov(anchor, prop, 默认)` | `Update` 可 patch |
| `Expr[T]`(含 `ClientVal`) | 客户端 | 内联 JS,引用 useState 变量 | `Update` 构造期报错;前端 `boundProps` warn+丢弃 |
| `ServerRef[T]`(ServerState 类字段) | 该字段 | `rt.ov("$s:类名", 字段, 默认)` | auto-diff/推送自动到达;`Update` 构造期报错 |
| Each 模板内的普通值(M2) | 构建期常量 | 字面量(模板 anchor 跨 item 共享,无 per-item 语义) | `Update` 对 `.$t[` anchor 构造期报错 |

M1 落地形态:

- `ClientVal[T]` 声明为 Page 类字段(`__init_subclass__` 收集、刻 owner、跨页复用报错);
  受控 prop 绑定(`Switch(checked=val)` / `Input(value=val)`)即唯一写者,编译为共用 useState;
  多写者/跨页引用/类型不匹配均为 CompileError,零绑定被引用发 UserWarning。
- `ServerState` 子类:类体注解即字段(必须带 JSON 可序列化默认值),单例(`$s:` 命名空间按类名
  寻址,类名冲突注册期报错)。`ServerField` 数据描述符:类访问 → `ServerRef[T]`,实例访问 → 纯 `T`,
  赋值 → TypeAdapter 校验 + auto-diff;注解写裸 `T`(实例语义诚实),描述符由 `__init_subclass__`
  运行期替换;`ServerRef` 的 `__bool__`/`__eq__` 抛错防误用。
- auto-diff 三态(contextvar sink):事件请求内的赋值记入 sink,随响应 envelope 下发——顺序为
  auto-diff 在前、显式 `Update` 在后,前端顺序 merge 故显式者覆盖(M0 兼容);请求外
  (后台任务——sink 带 closed 标志,spawn 任务继承的 contextvar 快照按已关闭处理)交给
  `PatchBus` → `GET /_shade/push` SSE。订阅先于快照、快照先于增量:merge 幂等,无需 patch 序号,
  重连即重收快照。SSE 跑在既有 ASGI 栈上,IPC 模式即一条常驻流式请求(Channel 帧),零新协议。

M2 落地形态(组件铺量期的所有权决策):

- **开合类 prop(Dialog/AlertDialog 的 `open`,Tabs 的 `value`)归客户端**:绑定 `ClientVal` 即受控
  (radix 的 `onOpenChange` 回写 = 唯一写者);普通值只作 `defaultOpen` 初始语义;禁止 `ServerRef`
  (双写者)。"服务端弹窗"记开放问题(§6)。
- **`Each` 循环容器**:items 只接受 `ServerRef[list[标量或扁平模型]]`,render-prop 构造期执行恰一次收
  类型化 `ItemProxy`(属性访问 → memoized `ItemRef` 叶子,按模型注解定型);模板 anchor 刻
  `{容器}.$t[i]`,事件共享 handlerId、payload 自动携带 `item_index`/`item_key`。数据流是**整表替换**:
  原地 `append` 不经过描述符赋值,惯用法 `chat.messages = [*chat.messages, msg]`;增量 splice、
  ClientVal 列表、嵌套 Each、per-item 受控状态均归 M3。模板白名单 Text/Button/Card。

### 3.4 表达式系统:SQLAlchemy 模式

`ClientState` 表达式采用 SQLAlchemy 式运算符重载构建表达式树,编译期翻译成 JS(M1 已实现,
`pyshade/expr.py`)。继承其二十年踩坑经验:

- `and`/`or`/`not` 无法重载(Python 语言限制),使用 `&`/`|`/`~`。
- `&` 优先级高于比较运算符的坑(`a == b & c == d` 解析为 `a == (b & c) == d`)双防线:
  `&`/`|` 构造期强制操作数为 bool 表达式(`b & c` 非 bool 立即 TypeError 并提示加括号);
  链式比较触发中间结果 `__bool__` 抛错。
- `__bool__`/`__len__`/`__iter__`/`__contains__` 全部抛 `TypeError`:表达式进入布尔上下文时
  立即报错并给出正确写法(`&`/`|`/`~` + 括号、`cond()` 收窄、测试用 `evaluate(snapshot)`),
  杜绝 Reflex 式"为什么 `if state.thinking:` 不生效"的静默困惑。`cond()` 是模块级函数:
  字面量在左(`True == expr`)导致 pyright 推导退化成 bool 时收窄回 `Expr[bool]`。
- 借鉴 `hybrid_property`:同一棵树双端求值——`to_js(scope)` 编译成 JS(复合子表达式一律加括号,
  与 JS 优先级解耦),`evaluate(snapshot)` Python 侧同语义求值,框架测试不必起 WebView。
- 类型标注:`ClientVal[T]` 诚实泛型(不做值代理——值代理会把 `~thinking` 推成 int,毁掉运算符
  推导);运算符用 self-type 约束,pyright 对 `~Expr[str]`、`Expr[bool] < Expr[bool]` 直接报错,
  与运行时构造期检查双层防线。受控组件值经 `value_of(component)` 进表达式
  (`ControlledMixin[T]` 提供推导);敏感组件不混入,类型层与运行时双层拒绝(§3.8)。
- 构造期定型:每个节点构造时确定类型(BOOL/STR/INT/FLOAT),跨类别比较、非 bool 逻辑运算、
  `str + int` 等在表达式构造的那一行即报错,不等到编译。

### 3.5 组件层:Pydantic DTO

- 为 shadcn 支持的元素抽公共基类,每个组件按其能力建子类继承。
- props 校验由 Pydantic 白拿;组件嵌套合法性用编译器规则表达(M2 已落地:声明式嵌套表驱动——
  `Tabs` 子组件必须全为 `TabItem`、`AccordionItem` 只能在 `Accordion` 内;`Dialog.trigger` 是
  标量组件槽(asChild 包裹,不得绑 `on_click`);`Tooltip` 是 wrapper 容器(恰一个宿主,宿主
  `visible` 保持默认);`Select`/`RadioGroup` 的选项走数据 prop(`list[Option]`,非组件树))。
- 枚举取值用 `StrEnum` / `Literal["default", "destructive", ...]` 定义,编译期同步生成 TS union type,
  两端共享单一 source of truth(M2 起 Each 项模型同源生成 TS interface)。shadcn 的 cva variant
  系统本身就是枚举驱动,映射自然。
- 类型注解完备度同时服务 IDE 补全和 AI 编码助手——这是采纳率因素,不是锦上添花。

### 3.6 按需打包与零 Node 管线(M2 已实现,`pyshade bundle`)

组件收集**从编译期 IR 拿,不做用户代码 import 静态分析**(原方案已否决):IR 精确知道每页用了哪些
组件,动态构造的组件树也被 IR 看到,"反射绕过收集"的问题面消失。按需由 import 图天然完成
(esbuild treeshake),`entry.tsx` 从 IR 组件集合生成;真正的逃生舱只剩
`ShadeApp(extra_components=[...])`(side-effect import 保住模块进图),`manifest.json` 记录组件清单。

用户环境只有 Python + pip,零 Node 的四个支点:

- **esbuild 官方二进制**:版本 pin + 每平台 sha256 表,首次使用从 npm registry 裸 HTTPS 下载 tarball
  (`PYSHADE_NPM_REGISTRY` 可换源,国内 npmmirror;`PYSHADE_ESBUILD_PATH` 离线兜底),用户级缓存,
  不随 wheel(保持 py3-none-any)。
- **vendor 物化进 wheel**:发版脚本以 npm `--omit=dev --ignore-scripts --install-strategy=hoisted`
  物化真实 `node_modules` 文件树(不做 ESM 预打包——radix 内部共享包会导致 React 双实例),
  经 `NODE_PATH` 解析,与 pnpm-lock 版本强校验。react 双形态经
  `--define:process.env.NODE_ENV` 死分支消除。
- **CSS 发版时预编译**:仓库内 `@tailwindcss/cli` 产出单 style.css 进 wheel,用户不碰 Tailwind。
  双层变量(`:root` 持值 + `@theme inline` 映射)保证预编译后运行时仍可换主题;`@source` 直接扫
  emitter 的 .py 字符串(v4 扫描器语言无关),CI 以 `check_css_coverage` 断言 golden/ui 全部 class 命中。
- **单一源码真相**:wheel 内 `pyshade/_frontend/` 由 hatch 构建钩子从 `frontend/` 注入
  (fresh checkout 无产物时不注入,editable 安装回退仓库布局);CI `bundle-zero-node` job 在
  剔除 node 的环境里以 wheel 安装打包并跑真机 E2E,与 vite 管线产物互为对照。

### 3.7 传输层:进程内 IPC,不走网络栈

- 壳层用 pytauri(见 3.9):Python 解释器经 PyO3 嵌入 Tauri 进程,前端 `pyInvoke` 经 Rust 直接调用
  进程内 Python 函数——连跨进程序列化都没有,不存在 socket,本机端口攻击面(local port scanning +
  CSRF 打 localhost)归零。
- **ASGI over IPC 需自建适配层**(已确认 pytauri 官方没有;其官方 FastAPI 集成示例
  `examples/nicegui-app` 反而是起 uvicorn 监听 localhost:8080、WebView 当浏览器访问——正是我们要
  避免的形态)。实现切入点:绕过 `Commands`,直接给 `BuilderArgs.invoke_handler` 传自定义 handler
  拿到原始 `Invoke`,把 command/headers/body 映射成 ASGI scope 喂 FastAPI,`resolve(bytes)` 回填响应。
  原语贴合度高:
  - headers 形态即 `list[tuple[bytes, bytes]]`,与 ASGI `scope["headers"]` 同构(docstring 直接对标 h11);
  - body 为 raw bytes;path/method 等元信息经 `pyfunc` header 或自定义 header 传递;
  - 流式响应(SSE、大 payload)用 Tauri Channel(已绑定 Python,`Channel.send` 有序推送);
  - FastAPI app 跑在 pytauri 的 anyio BlockingPortal 子线程事件循环里(asyncio/trio 皆可),
    无 uvicorn、无 socket。
- 已知限制:拦截面仅限 `plugin:pytauri|pyfunc` 这一条 Tauri command(拦不到 Tauri 内置 IPC 与自定义
  URI scheme,后者 pytauri 未绑定);body 只接受 Raw bytes(前端负责 JSON→bytes,pytauri 前端 SDK
  本就如此)。
- 开发模式可额外起真 HTTP server 便于调试;生产构建只留 IPC。两种模式跑同一个 ASGI app,行为一致。
- **适配器 shutdown 取消 in-flight 请求**(M2 实测教训):开放式流(SSE 推送)的 bridge task 永不
  自行结束,而 `start_blocking_portal` 正常退出会等全部 task 完成——不取消则关窗后进程挂死;
  Channel 单向,JS 侧取消无法回传,唯一正确的终结点就是 adapter lifespan 退出。
- FastAPI 是实现细节,对用户完全隐藏:不暴露 app 实例,docs/openapi 路由默认不存在
  (NiceGUI < v2.8.0 曾默认暴露 Swagger/OpenAPI,该 bug 由本项目作者修复,引以为鉴)。

### 3.8 安全默认(默认行为,不是可选项)

- 敏感字段使用 `SecretStr` 类 DTO 字段:日志、repr、debug 输出自动脱敏。
- 敏感输入**不进协议**:密码框等组件的中间态永远留在前端,框架保证此类组件不产生 keystroke 级事件,
  仅在 submit 时作为一次性 payload 跨界。
- 无 TCP 端口(见 3.7)。

### 3.9 壳层:pytauri(2026-07-14 评估定案)

采用 pytauri,自研 WebView 绑定不在范围内。评估要点:

- 架构:PyO3 进程内嵌入(非跨进程 IPC),command 层自带 Pydantic 请求/响应校验
  (`@commands.command()`,官方自称 "inspired by FastAPI"),原生 anyio 异步。
- 插件:19 个官方 Tauri 插件有 Python 绑定;托盘/菜单是核心级绑定;updater/dialog/notification 齐全。
  缺 sql/store/log 等,对 PyShade 无影响。
- 打包:官方主推 Tauri bundler + python-build-standalone(便携 CPython 作为 Tauri resource 嵌入),
  三平台产出 msi/nsis/dmg/AppImage/deb;另有 `pytauri-wheel` 免 Rust 编译器路径。
- 可借鉴:`_gen_ts.py` 已实现 Python→TS 类型与 IPC client 代码生成,枚举同源(3.5)直接参考。
- 版本策略:pytauri 当前 v0.8.0、pre-1.0、约月度 minor 且常带 breaking change,锁定 minor 跟进,
  升级作为显式任务处理。许可证 Apache-2.0,MIT 项目依赖无问题。

### 3.10 文档:单点真相 + dogfooding

- 组件即 Pydantic model,`model_json_schema()` 直接产出结构化 props 表(字段、类型、默认值、约束、枚举取值),
  无需 docstring 解析。
- 同一 schema 生成三份产物:文档站(人)、llms.txt(AI)、类型存根(IDE)。
- i18n 红利:结构化部分语言无关,只有描述文本需要翻译,维护量远小于全手写文档。
- 编译器提供 desktop 和 web 两个 target,文档站用自家 web target 构建——dogfooding,
  每个组件的 live demo 同时是最大的集成测试。

### 3.11 多页面路由(M2 定案)

- **route 归客户端**:`navigate(Page 类或类名字符串)` 赋给事件 prop,编译为 `rt.navigate("页面名")`,
  零 IPC、不进 EventRegistry;字符串目标是互相导航时前向引用的官方姿势,`check_app` 编译期校验
  目标存在,不牺牲安全性。服务端导航是 handler 返回 `Navigate(...)`,编码为保留地址 `$nav` 的
  patch(patch 协议的保留字,非新协议),与数据 patch 同 envelope 到达。
- **App 级共享 store**:`app.gen.tsx` 只聚合参数与页面表(boundProps 全页聚合、push 任一页需要即开、
  初始页 = `pages[0]`),骨架是手写 runtime(`ShadeAppProvider` + `ShadeRouter`)。overrides 提升
  App 级——服务端 `Update` 不因切页蒸发;push 订阅提升 App 层——切页不断连、他页停留时后台推送不丢。
  `usePageRuntime` 双模式:有 Provider 消费共享 store,无 Provider(单页挂载/单测)回落页面本地。
- **页面状态 unmount 即丢(定案)**:ClientVal/受控输入随页面卸载重置,跨页存活的归宿是 ServerState;
  keep-alive 与深链归 M3。页面类名是 anchor/handlerId/路由的共同命名空间,重复即 CompileError。

## 4. 已知风险与预期管理

- **包体**:去掉 Chromium 后瓶颈转移到 Python 运行时,PyInstaller/Nuitka 产物 30-50MB 起步。
  远好于 Electron 150MB+,但到不了 Tauri 纯 Rust 的 5MB 量级。宣传口径不对标 Tauri 包体数字。
- **dev loop 速度**:编译路线的第一体验指标。esbuild 侧很快,慢点通常在 Python 侧代码生成——
  增量编译(只重编译改动的组件树)必须早做,Reflex 因编译慢被诟病多年。
- **表达式子集的 DX 代价**:`ClientState` 表达式不是真 Python,文档需在最前面讲清边界;
  编译器报错信息质量是核心 DX 投资。
- **状态同步粒度**:哪些状态留前端、哪些事件回传 Python,这条线必须在 M0 划清并验证输入延迟,
  否则后续全是补丁。
- **平台兼容**:各系统 WebView(WebView2 / WKWebView / WebKitGTK)行为差异,需要兼容性测试矩阵。
  已知坑:macOS 上 python-build-standalone 的 `libpython3.dylib` 缺 `@rpath` install_name,需
  `install_name_tool` 修补(pytauri 文档有 workaround);Linux 基线 glibc ≥ 2.35(Ubuntu 22+),
  WebKitGTK 依赖若打进 wheel 体积约 10MB → 100MB;**frontendDist 必须传相对
  src_tauri_dir 的路径**——Windows 盘符绝对路径(`C:/...`)会被 Tauri 的 untagged
  `FrontendDist` 反序列化误判为 URL(scheme `c:`),页面静默加载失败(M1 实测踩坑)。
- **上游 pre-1.0**:pytauri 月度 minor 常带 breaking change,需锁版本、升级走显式任务;
  其 `plugin:pytauri|pyfunc` 单命令拦截面是 ASGI 适配器的硬约束。

### 4.1 真机实测数据(2026-07-14,Windows / WebView2 139,pyshade.testing 自动化采集)

M0 七项验证全部通过(隐藏窗口 `visible:false`,JS 正常执行,`document.visibilityState`
仍为 visible)。数字由 `tests/e2e_native` 每次 CI 在 windows runner 复测:

- **事件 RTT(进程内 IPC,bench_echo × 100)**:p50 = 1.2ms,p95 = 2.0ms,max = 2.7ms
  ——验收线 p50<5ms / p95<20ms,实测优一个数量级,对比 NiceGUI WebSocket 路径的核心优势成立。
- **键入延迟(受控输入 30 字符,合成事件)**:sync p95 = 0.6ms,fence(含 effect flush)
  p95 = 6ms(验收线 50ms);键入期间 IPC 计数恒为 0,blur 恰触发 1 次事件——0-keystroke-IPC
  架构目标达成。
- **headers 透传**:path/query 至 64KB 无截断(验收线 8KB);64 个自定义 header 无丢失。
- **payload**:双向 32MB 完整(sha256 校验);8MB 下行 78ms / 上行 97ms。
- **流式竞态**:50 并发快速流(每流 20 帧)零丢帧/乱序/重复——shadeFetch 的帧缓冲设计有效。
- **空 body**:`Uint8Array(0)` 确认落为 `InvokeBody::Raw`,不被 reject。
- **窗口关闭中流**:`channel.send` 对已销毁 webview 抛异常,bridge 正常 abort 流,
  进程稳定无死锁——无需额外防护。

## 5. 里程碑

- **M0 — 端到端可行性验证**(风险集中释放):
  3-5 个组件(必含一个受控输入组件)、编译器雏形(Python DTO → React 代码生成)、pytauri 壳跑通、
  ASGI over IPC 适配器雏形(自定义 `invoke_handler` → ASGI scope → FastAPI,含 Channel 流式验证)、
  IPC 事件回传闭环、验证输入延迟可接受。
- **M1 — 表达式系统与编译期校验**(已完成,详见 §3.3/§3.4):
  `ClientState`/`ServerState`、SQLAlchemy 式表达式树、嵌套合法性/事件签名/死引用检查、`__bool__` 抛错;
  另交付 `pyshade.testing` 真机 E2E 框架 + GitHub Actions CI(§4 实测数字来源)。
  未进 M1(移交 M2+):`Each` 循环容器、受限闭包 handler、多页面路由。
- **M2 — 组件铺量与按需打包**(已完成,详见 §3.3/§3.5/§3.6/§3.11):
  22 个组件(三波:复刻/选项与数值受控/容器浮层)、零 Node 打包管线(`pyshade bundle`,esbuild
  二进制 + wheel 内 vendor + CSS 预编译)、多页面路由(`navigate`/`Navigate`/`$nav`)、`Each`
  循环容器(整表替换 + item_index 事件)。examples:component_gallery(生成代码过真实 tsc)、
  task_board(路由 + Each 真机 E2E)。未进 M2(移交 M3):受限闭包 handler、`--watch`、
  theme 主题口子、Each 嵌套/增量/per-item 受控、keep-alive 与深链。
- **M3 — 打包分发链**:
  python-build-standalone + Tauri bundler(pytauri 官方路径),三平台(Windows/macOS/Linux)
  安装包产出;处理 macOS rpath 修补与 Linux glibc 基线。
- **M4 — 文档站与发布**:
  schema 生成 props 表、llms.txt、web target dogfooding 文档站、PyPI 发布。

M0 是风险所在,M2 之后是体力活;先验证再铺量。

## 6. 开放问题

- ASGI over IPC 适配器是否作为独立包发布(如 `pytauri-asgi`),回馈 pytauri 生态并摊薄维护成本。
- 热重载设计:编译路线下 dev 模式的增量编译与状态保持;pytauri standalone 模式下 Python 代码变更
  需重装的问题如何规避(dev 用 editable install)。
- shadcn 上游同步策略:shadcn 组件源码更新后,PyShade 内置副本如何跟进。
- Tailwind 主题暴露边界:只暴露 CSS 变量层(shadcn token),Python 用户不碰 Tailwind class——具体 API
  待设计(双层变量的运行时可覆盖性已在 §3.6 打底,`ShadeApp(theme=...)` 口子未做)。
- 服务端弹窗:`open` 归客户端所有(§3.3),服务端想主动弹窗(全局错误/更新提示)缺正门,
  语义与 `$nav` 类似的保留地址是候选。
- web target 的优先级:仅服务文档站,还是作为正式发布特性。

已关闭的问题(结论回填正文):pytauri 成熟度评估 → 3.9;Python 打包工具选型 → 不用
PyInstaller/Nuitka,走 python-build-standalone + Tauri bundler(3.9 / M3);流式协议设计 →
PSA1 封包 + Channel 帧(§3.7 / §4 实测),SSE 直接复用 ASGI 流式分支(§3.3 推送通道),
WebSocket 语义 M1 未见需求,不引入。
