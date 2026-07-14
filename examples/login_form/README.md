# login_form — PyShade M0 端到端验证

登录表单示例:六组件(Text/Button/Input/PasswordInput/Switch/Card)+ 事件回传 + Python 更新 UI。

## 自动化测试(不需要 WebView)

从项目根目录运行:

```bash
uv run pytest tests/e2e/ -q
```

覆盖:事件路由全链路(submit/change/toggle/unknown/422)、编译器产物验证、安全默认验证。

## 真机运行(需要 WebView2)

1. 编译前端产物:

```bash
uv run pyshade build login_form.app:app --out frontend/src/generated
```

2. 启动 Vite dev server:

```bash
pnpm -C frontend dev
```

3. 启动 PyShade(dev 模式,pytauri-wheel 壳):

```bash
PYSHADE_DEV=1 uv run python -m login_form
```

4. 延迟测量(在 WebView DevTools console):

```js
// 键入 IPC 计数(应为 0)
window.__PYSHADE_IPC_COUNT__

// 事件 RTT 基准
await window.__pyshadeBench(100)
```
