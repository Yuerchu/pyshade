# task_board

PyShade M2 演示:**多页面路由 + Each 列表渲染 + 服务端 Navigate**。

- `BoardPage`:`Each(BoardState.tasks, render=..., key='id')` 渲染任务卡片;模板按钮共享
  handlerId,`ctx.item_key` 定位数据;新增任务用整表替换
  `board.tasks = [*board.tasks, item]`(原地 append 不触发 auto-diff)。
- `StatsPage`:`navigate('BoardPage')` 字符串目标(互相导航的前向引用姿势);
  "清理已完成并返回" 演示 handler 返回 `Navigate(...)` —— `$nav` patch 与数据 patch
  同一 envelope 到达,前端先合并数据再切页。
- 页面状态 unmount 即丢;跨页存活的是 ServerState(切页后列表与统计不蒸发)。

## 运行

```bash
uv run pyshade build task_board.app:app --out frontend/src/generated  # PYTHONPATH=examples/task_board/src
pnpm -C frontend build
uv --project examples/task_board run python -m task_board
```

零 Node 打包(esbuild 管线):

```bash
uv run pyshade bundle task_board.app:app --out dist-board
```
