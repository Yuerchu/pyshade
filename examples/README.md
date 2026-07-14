# examples

- [login_form](login_form/) — M0 端到端验证:登录表单(六组件 + 事件回传 + Python 更新 UI)
- [settings_panel](settings_panel/) — M1 全特性演示:客户端表达式(零 IPC 联动)+ ServerState
  auto-diff + 后台任务 SSE 推送

`frontend/src/generated` 一次只承载一个示例:
`uv run pyshade build <包名>.app:app --out frontend/src/generated` 后再构建/启动前端。
