# examples

- [login_form](login_form/) — M0 端到端验证:登录表单(六组件 + 事件回传 + Python 更新 UI)
- [settings_panel](settings_panel/) — M1 全特性演示:客户端表达式(零 IPC 联动)+ ServerState
  auto-diff + 后台任务 SSE 推送
- [component_gallery](component_gallery/) — M2 组件画廊:四页铺开全部 22 个组件 + Each + 路由,
  CI 对生成代码跑真实 tsc
- [task_board](task_board/) — M2 路由 + Each 演示:多页导航(客户端 navigate + 服务端 Navigate)、
  Each 列表(item_key 定位、整表替换),真机 E2E 驱动

`frontend/src/generated` 一次只承载一个示例:
`uv run pyshade build <包名>.app:app --out frontend/src/generated` 后再构建/启动前端。
零 Node 路径不占用该目录:`uv run pyshade bundle <包名>.app:app --out dist-xxx`。
