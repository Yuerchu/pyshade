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
| `_const_props` 声明的 prop(M4,'const') | 构建期常量 | 字面量(编译期渲染进产物,如 Link.href、Heading.level、Markdown.source) | `Update` 构造期报错 |

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
  主题口子(M3 亮色 / M4 暗色):`ShadeApp(theme=Theme(..., dark=ThemeTokens(...)))` 只暴露
  CSS 变量层——token 全量镜像 :root 与 .dark(对账测试双向锚定,radius 是模式无关 token),
  compile 发 `theme.gen.css` 三段(`:root` 模式无关 / `:root:not(.dark)` 亮色——specificity
  保证内联后到不压过内置暗色默认 / `.dark` 暗色)、bundle 内联 `<style>`(三件套契约不变),
  值原样透传 + 注入护栏。dark: utility 经 `@custom-variant dark` 走 class 策略。
- **单一源码真相**:wheel 内 `pyshade/_frontend/` 由 hatch 构建钩子从 `frontend/` 注入
  (fresh checkout 无产物时不注入,editable 安装回退仓库布局);CI `bundle-zero-node` job 在
  剔除 node 的环境里以 wheel 安装打包并跑真机 E2E,与 vite 管线产物互为对照。
- **bundle 窄版增量(M4)**:staging 指纹((相对路径,size,mtime_ns) 哈希,wheel 布局恒命中)
  跳 copytree;esbuild 输入内容哈希(staged 指纹 + generated/entry/tsconfig 全部内容 +
  esbuild 版本与参数)命中 `.bundle-stamp.json`(成功后才写,崩溃安全)即跳全量构建;
  `PYSHADE_BUNDLE_FRESH=1` 逃生。index.html/style.css 每次照常重写(theme/scheme/dev-client
  注入不受跳过影响)。实测 task_board:冷 78ms(staging 15/esbuild 63)→ 热 31ms [skipped];
  dev loop 最常见的"改 handler 不改 UI"代数吃满该收益,剩余延迟 = 解释器 + import 地板。

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

### 3.10 文档:单点真相 + dogfooding(M4 落地形态)

- 组件即 Pydantic model,props 表数据源是 **`model_fields` 内省**(`pyshade.docs.introspect`),
  不走 `model_json_schema()` 直出——JSON schema 表达不了绑定所有权(§3.3 五分类)与 EventSpec
  事件语义,is-instance union 只会产出无信息的 anyOf。内省给到:注解拆 union → 绑定形态、
  默认值、枚举取值、事件 kind、`Field(description=...)` 描述;`collect_components()` 与编译器
  EMITTERS 双向对账(加组件缺 emitter / 缺 DTO 即抛)。
- **描述语言分层**:`Field(description=英文)` 是 canonical(IDE hover / 生态直读),
  中文翻译表放文档站侧(键集合对账防漂移);类级 docstring 保持中文。
- `model_json_schema()` 本身对用户可用(Expr/ServerRef/ClientAction 给宽松占位 schema,
  EventSpec 以 Annotated 元数据钩子占位 Callable),但只是兼容口,不是文档数据源。
- 同一内省数据生成三份产物:文档站(人)、llms.txt(AI)、类型存根(IDE,M4+)。
- i18n 红利:结构化部分语言无关,只有描述文本需要翻译,维护量远小于全手写文档。
- 编译器提供 desktop 和 web 两个 target,文档站用自家 web target 构建——dogfooding,
  每个组件的 live demo 同时是最大的集成测试。
- **静态站 demo mock(M4 文档站,显式决策)**:CF Pages 静态托管无 Python 后端,
  `shadeFetch` 浏览器分支先问 `window.__PYSHADE_MOCK__(path, init)`——返回 Response 即短路
  (事件 envelope / push SSE 全链路照常),undefined 回落真实 fetch。文档站的
  demo-mock.js 按 handlerId 复刻 handlers.py 行为——接受"违背单点真相"的双份维护
  (用户拍板),键集合对账测试兜"缺口",行为漂移靠 `pyshade dev`(真后端)人工走查。
- **web target 最小形态(M4):`pyshade serve`**——生产 bundle + 单进程 uvicorn,
  dispatcher = `/_shade/*` → FastAPI(事件 + SSE 推送),其余 → 静态三件套
  (`web/_serve.make_web_asgi`;dev dispatcher 复用它再叠 dev 路由)。共享语义如实声明:
  ServerState 是进程级单例(§3.3),多浏览器客户端共享同一份状态宇宙(请求外变更经
  PatchBus 广播、重连快照收敛);per-visitor session 隔离是独立工作线(§6),
  读多写少的站点(文档站)可直接用。

### 3.11 多页面路由(M2 定案)

- **route 归客户端**:`navigate(Page 类或类名字符串)` 赋给事件 prop,编译为 `rt.navigate("页面名")`,
  零 IPC、不进 EventRegistry;字符串目标是互相导航时前向引用的官方姿势,`check_app` 编译期校验
  目标存在,不牺牲安全性。服务端导航是 handler 返回 `Navigate(...)`,编码为保留地址 `$nav` 的
  patch(patch 协议的保留字,非新协议),与数据 patch 同 envelope 到达。
- **App 级共享 store**:`app.gen.tsx` 只聚合参数与页面表(boundProps 全页聚合、push 任一页需要即开、
  初始页 = `pages[0]`),骨架是手写 runtime(`ShadeAppProvider` + `ShadeRouter`)。overrides 提升
  App 级——服务端 `Update` 不因切页蒸发;push 订阅提升 App 层——切页不断连、他页停留时后台推送不丢。
  `usePageRuntime` 双模式:有 Provider 消费共享 store,无 Provider(单页挂载/单测)回落页面本地。
- **页面状态默认 unmount 即丢**:ClientVal/受控输入随页面卸载重置,跨页数据的正门是 ServerState。
  **keep-alive(M3 已落地)**:`ShadeApp(keep_alive=True)` 时访问过的页面保持挂载
  (display:none 包裹,不用 React `<Activity>`——语义可预期,Activity 记升级路径),
  本地状态跨切页存活;已知限制诚实文档——portal 浮层(Dialog/Tooltip)渲染进 body
  不受隐藏包裹约束、不保证滚动位置。页面类名是 anchor/handlerId/路由的共同命名空间,重复即 CompileError。
- **深链(M3 已落地)**:`#/PageName` hash 路由。生成的 App 恒开(pageNames 校验 + deepLink),
  runtime 默认关(testkit 双 Provider 同 document 不串扰的前提);启动 hash 覆盖初始页
  (replaceState 规范化),navigate 直赋 hash(历史条目,浏览器后退可用),hashchange 反向驱动,
  无效目标 warn + 忽略不回写。打包 WebView 无地址栏 → 恒回落 pages[0],为 web target 铺路。
- **color scheme 归客户端(M4 dark mode,route 的平行先例)**:纯呈现态、零 IPC、服务端不可
  patch。class 策略(documentElement 挂 `.dark`,应用内切换必须 class,系统跟随由 runtime
  解析后落 class);`ShadeApp(color_scheme='system'|'light'|'dark')` 是默认值,localStorage
  只存显式选择('system' 清键回到跟随系统)。切换器不做内置组件——`set_color_scheme()` /
  `toggle_color_scheme()` 是与 navigate 同族的零 IPC action(ClientAction 基类:__bool__/
  __call__ 抛错 + is_instance schema),赋给事件 prop 编译为 `rt.setColorScheme(...)`,
  不进 EventRegistry;submit=True 与之互斥(CompileError)。bundle 的 index.html 恒注入
  head 内联 boot script(与 runtime 同解析规则)防首帧白闪。

### 3.12 打包分发链(M3 已实现,`pyshade init` + `pyshade package`)

pytauri-wheel 只能跑不能分发(venv 依赖),安装包必走 full pytauri + Rust;PyShade 把官方
五步收编成两条命令,打包机 = Python + Rust,**零 Node**(tauri-cli 走 `cargo install`,
beforeBuildCommand 留空,frontendDist 用 `pyshade bundle` 产物)。

- **frontendDist 烤入二进制**(定案):standalone 的 `context_factory` 忽略一切运行时参数
  (Rust 侧 `|_args,_kwargs| tauri_generate_context()`),运行时覆盖不可达;`pyshade package`
  把 bundle 三件套拷进 `src-tauri/frontend`,经 `tauri.conf.json` 的 `"./frontend"` 编译期固化。
- **双配置分工**:`src/<pkg>/Tauri.toml` 是 dev 态真相(pytauri-wheel 读),
  `src-tauri/tauri.conf.json` 是打包真相(init 时从前者推断生成,package 体检比对漂移 warn);
  `bundle.resources` 只写 `src-tauri/tauri.bundle.json`——写进 tauri.conf.json 会让
  `tauri dev` 误链复制出的 Python 环境(pytauri 官方警告),配合独立 `bundle-release` profile 隔离。
- **便携 CPython 单版本 pin**(python-build-standalone install_only_stripped):与打包机
  Python 解耦,六平台 tarball sha256 表(`scripts/pin_cpython.py` 从官方 SHA256SUMS 生成),
  用户缓存 + `.pyshade-stamp` 增量;镜像/离线/自选版本经 env 逃生。
- **运行时 shim**(`pyshade.shell.run`):`sys._pytauri_standalone`(pytauri standalone 协议)
  选择 factories 来源,双形态共用 EventRegistry → FastAPI → AsgiIpcAdapter 装配;
  `PYSHADE_SMOKE=1` → Ready 即退出(CI 冒烟);`freeze_support` 防 spawn 循环。
- **实测教训**:`tauri-plugin-pytauri` 必须是模板 Cargo.toml 的直接依赖(capability 权限经
  cargo links metadata 只向直接依赖方暴露);运行期生成的 .pyc 不在 NSIS 装载清单内、卸载
  残留 → package 前 compileall 预编译;pytauri-wheel 混进 pyembed 是 +30MB 纯冗余 →
  examples 把它挪到 dev 依赖组,packager 检测并 warn。
- Linux 默认只出 deb:AppImage 的 libpython 挪位(tauri#11898)未验证,rpath 已加
  `$ORIGIN/../lib` 对冲,显式 `--bundles appimage` 可尝试。签名/公证 out of scope(§6)。
- 实测(Windows):安装包 27.2MB(NSIS,per-user 安装到 `%LOCALAPPDATA%`),
  首次全量编译 ~9min、增量 ~1min,pyembed 命中缓存的一键 package 83s。

### 3.13 内容组件(M4:Heading / Link / Markdown / CodeBlock / Stack)

文档站与长文场景的最小集,List/Table 由 Markdown 表达,Image 不做(静态资产管线缺失,§6)。
Stack 是纵向布局容器(无边框卡片语义,width 档位 sm/md/lg/full 构建期定档 'const'):
Card 恒 max-w-sm 承载不了文档流,Stack 补上"页面级内容列"这一层。

- **'const' binding(§3.3 第五类)**:`Component._const_props` 声明的 prop 是构建期常量——
  Markdown.source / CodeBlock.code,language / Link.text,href / Heading.level 在编译期渲染进
  产物,运行时 patch 必然静默失效,故 `Update` 构造期拒绝、emitter 内联字面量(不发 rt.ov)。
  Heading.text 保持 Text 同款三态(plain/Expr/ServerRef)。
- **markdown 编译期渲染**:mistune v3(table/strikethrough/task_lists 插件)+ pygments 高亮,
  挂 `pyshade[content]` extra(pygments ~4MB 不进主依赖/standalone 安装包);编译器惰性
  import,缺失报 CompileError 带安装提示;未知语言编译期报错。**escape=True 一律拒绝
  raw HTML**(无逃生口)——内容虽是构建期作者可控,不给"将来内容源不可控"留新决策点;
  运行时动态 markdown(LLM 输出类场景)不支持,记 §6。
- **样式两条线**:Markdown 产物挂 `prose prose-neutral dark:prose-invert max-w-none`
  (@tailwindcss/typography,只进发版 CSS 预编译,零用户侧 Node/运行时依赖;emitter 字符串
  经 @source 扫描命中);代码高亮的 pygments 短 class(k/s1/c1…)经 `.shade-hl` 后代选择器
  作用域化,token 变量定义在 .shade-hl 自身作用域(不进 :root,不扰 Theme 对账),
  `.dark .shade-hl` 提供暗色。
- **Link 语义**:仅外链(http(s)/mailto,构造期校验),应用内跳转的正门是 navigate(§3.11);
  桌面 WebView 上外链应转系统浏览器打开,M4 未解,记 §6。

## 4. 已知风险与预期管理

- **包体**:去掉 Chromium 后瓶颈转移到 Python 运行时,PyInstaller/Nuitka 产物 30-50MB 起步。
  远好于 Electron 150MB+,但到不了 Tauri 纯 Rust 的 5MB 量级。宣传口径不对标 Tauri 包体数字。
- **dev loop 速度**:编译路线的第一体验指标。实测慢点不在 Python 代码生成(ms 级)而在
  worker 解释器 + 框架 import 地板与 esbuild;M4 窄版增量(§3.6)吃掉 staging/esbuild 的
  重复开销,更激进的路径(常驻 esbuild --watch / worker 复用)已评估并明确不做(§6)。
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
- **M3 — 打包分发链**(已完成,详见 §3.12/§3.11/§3.6):
  `pyshade init` + `pyshade package` 两条命令出三平台安装包(打包机 = Python + Rust,零 Node;
  macOS rpath 修补与 Linux rpath 已内建);release workflow 三平台 matrix + 主 CI Windows
  打包冒烟。搭车交付:`pyshade dev`(supervisor/worker 整代重启 + generation SSE 自动刷新,
  取代从未工作的 `bundle --watch`)、路由 keep-alive、`#/PageName` 深链、theme 主题口子。
  未进 M3(移交 M4+):签名/公证、dark mode、窗口热重载、AppImage 验证、
  受限闭包 handler、Each 增强、服务端弹窗。
- **M4 — 文档站与发布**:
  schema 生成 props 表、llms.txt、web target dogfooding 文档站、PyPI 发布。

M0 是风险所在,M2 之后是体力活;先验证再铺量。

## 6. 开放问题

- ASGI over IPC 适配器是否作为独立包发布(如 `pytauri-asgi`),回馈 pytauri 生态并摊薄维护成本。
- 原生窗口热重载:M3 定案 `pyshade dev` 面向浏览器(窗口进程即 Python 进程,重启必关窗;
  "壳+子进程 server"是 §3.7 否决的形态);窗口侧的热重载路径仍开放。dev loop 增量编译的
  窄版已落地(§3.6,M4);明确不做:常驻 `esbuild --watch`(跨进程时序/双写者/Windows
  文件锁,收益仅 100-300ms)、esbuild JS context API(要 Node,违反零 Node)、worker
  复用(§3.12 `_STATE_CLASSES` 硬约束)、per-page 增量 emit(compile 本就 ms 级,无肉)。
- shadcn 上游同步策略:shadcn 组件源码更新后,PyShade 内置副本如何跟进。
- 安装包签名/公证(macOS notarization / Windows 代码签名):M4+;当前 release notes
  附未签名产物的打开指引。
- 服务端弹窗:`open` 归客户端所有(§3.3),服务端想主动弹窗(全局错误/更新提示)缺正门,
  语义与 `$nav` 类似的保留地址是候选。
- web target 的深化:最小形态 `pyshade serve` 已落地(§3.10,M4);开放点是 per-visitor
  session 隔离(要动 ServerState 单例/全局 publisher/快照全套,非小补丁)与生产化增强
  (gzip/cache 头/多 worker)。
- Link 外链在桌面 WebView 应转系统浏览器打开(当前 target="_blank" 行为依 WebView 而定),
  需要壳层 opener 接线(§3.13)。
- 运行时动态 markdown(ServerRef 驱动的内容,LLM 聊天类场景):当前 Markdown 是编译期
  const,动态化需要前端运行时渲染器,违背零运行时依赖,暂不做(§3.13)。
- Image 与静态资产管线:bundle 三件套契约没有资产拷贝/寻址机制,Image 组件依赖它(§3.13)。

已关闭的问题(结论回填正文):pytauri 成熟度评估 → 3.9;Python 打包工具选型 → 不用
PyInstaller/Nuitka,走 python-build-standalone + Tauri bundler(3.9 / M3);流式协议设计 →
PSA1 封包 + Channel 帧(§3.7 / §4 实测),SSE 直接复用 ASGI 流式分支(§3.3 推送通道),
WebSocket 语义 M1 未见需求,不引入;主题 dark mode → class 策略 + 零 IPC action +
localStorage 显式选择(§3.6 / §3.11,M4)。
