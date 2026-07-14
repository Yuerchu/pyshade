# settings_panel — PyShade M1 全特性演示

同一页面演示 prop 的四种绑定形态(design.md §3.3 所有权公理):

| 形态 | 页面里的例子 | 行为 |
|---|---|---|
| 普通值 | `Card(title='设置面板')` | 服务端所有,`Update` 可 patch |
| `ClientVal` / 表达式 | `Input(disabled=~thinking)`、`Text(visible=thinking & dark)` | 编译成内联 JS,交互期间零 IPC |
| `value_of()` | `Text(text='思考力度:' + value_of(effort))` | 受控组件值作为表达式源 |
| `ServerRef` | `Text(text=PanelState.status)` | handler 直接给字段赋值,auto-diff 随响应下发;后台任务经 SSE 推送 |

交互看点:

- 拨动"思考模式"/"深色模式"、输入昵称——所有联动都在前端完成,`window.__PYSHADE_IPC_COUNT__` 不增长;
- 点"保存设置"——`on_save` 里只有 `panel.status = ...` 赋值,没有 `Update`,UI 照样更新(auto-diff);
- 点"运行后台任务"——响应立即返回,进度条文本每 0.6s 经 `GET /_shade/push` SSE 推送到达。

## 自动化测试(不需要 WebView)

从项目根目录运行:

```bash
uv run pytest tests/e2e/test_settings_panel_example.py -q
```

## 真机运行(需要 WebView2)

1. 编译本示例到前端 generated 目录:

```bash
uv run pyshade build settings_panel.app:app --out frontend/src/generated
```

2. 启动 Vite dev server:

```bash
pnpm -C frontend dev
```

3. 启动 PyShade(dev 模式,pytauri-wheel 壳):

```bash
PYSHADE_DEV=1 uv run python -m settings_panel
```

生产形态则用 `pnpm -C frontend build` 后直接 `uv run python -m settings_panel`。

注意:`frontend/src/generated` 一次只承载一个示例,切换示例前重跑第 1 步
(仓库默认提交的是 login_form 的产物,CI 也按 login_form 构建)。
