"""事件处理器:模块级具名函数,由 EventRegistry 收集。

on_save:事件内给 ServerState 字段赋值 → auto-diff 随响应 envelope 下发,不写 Update。
on_run_job:响应立即返回,后台任务的赋值经 PatchBus → GET /_shade/push SSE 到达前端。
"""

import asyncio

import anyio

from pyshade.events import EventContext
from settings_panel.state import panel

# fire-and-forget 任务持引用防 GC;portal loop 是 asyncio,create_task 是此处的非结构化 spawn 出口
_background_tasks: set['asyncio.Task[None]'] = set()

JOB_STEP_SECONDS = 0.6


def on_save(ctx: EventContext) -> None:
    nick = str(ctx.values.get('nick', ''))
    panel.save_count = panel.save_count + 1
    suffix = f',欢迎 {nick}' if nick else ''
    panel.status = f'已保存(第 {panel.save_count} 次){suffix}'


async def on_run_job(ctx: EventContext) -> None:
    panel.status = '后台任务运行中…'  # 仍在事件请求内:随本次响应下发
    task = asyncio.create_task(_fake_job())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _fake_job() -> None:
    # 此协程在响应发出后运行:sink 已 closed,赋值走推送通道
    for percent in (20, 40, 60, 80, 100):
        await anyio.sleep(JOB_STEP_SECONDS)
        panel.progress = f'进度 {percent}%'
    panel.status = '后台任务完成'
    panel.progress = ''
