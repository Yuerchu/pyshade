"""NativeHarness:自驱动真机 E2E 的生命周期编排。

pyshade.testing 中唯一接触 pytauri 的模块(全部惰性 import)。
流程:隐藏窗口启动 → Ready → eval 注入 testkit(幂等 guard + 重试)→ 页面执行
→ report 经 IPC 回传 → case 5(关窗观察)→ 组装报告(JSON + Markdown)。
一进程最多 run 一次(tao EventLoop 限制)。
"""

import json
import os
import platform
import threading
import time
import uuid
from importlib.metadata import version as pkg_version
from os import environ
from pathlib import Path
from typing import Any

from anyio.from_thread import start_blocking_portal
from fastapi import FastAPI
from loguru import logger as l

from pyshade.asgi import AsgiIpcAdapter
from pyshade.testing._collector import ReportCollector
from pyshade.testing._config import HarnessConfig
from pyshade.testing._report import CaseResult, EnvInfo, TestReport, apply_thresholds
from pyshade.testing._routes import mount_test_routes

_CLOSE_GRACE_S = 15.0
_OBSERVE_AFTER_CLOSE_S = 5.0


class NativeHarness:
    """把一个 FastAPI app 装进 pytauri 隐藏窗口并跑完 testkit 全案。"""

    _ran: bool = False

    def __init__(self, app: FastAPI, config: HarnessConfig) -> None:
        self._app = app
        self._config = config
        self.collector = ReportCollector()
        self._app_handle: Any = None
        self._close_requested = threading.Event()
        self._captured_logs: list[str] = []

    def close_window(self) -> None:
        """HarnessActions:case 5 的关窗动作(由测试路由在 portal loop 调用)。"""
        self._close_requested.set()
        from pytauri import Manager

        window = Manager.get_webview_window(self._app_handle, self._config.window_label)
        if window is not None:
            window.close()

    def _window_config(self) -> dict[str, Any]:
        cfg: dict[str, Any] = {
            'label': self._config.window_label,
            'title': 'pyshade-testing',
            'width': 480,
            'height': 640,
        }
        if self._config.visibility == 'hidden':
            cfg['visible'] = False
        elif self._config.visibility == 'offscreen':
            cfg.update({'visible': True, 'x': -32000, 'y': -32000})
        return cfg

    def _inject_source(self) -> str:
        bundle = self._config.testkit_bundle.read_text(encoding='utf-8')
        run_config = json.dumps(self._config.run_config, ensure_ascii=False)
        return (
            '(function(){'
            'if (window.__pyshadeTestkitBooted) return;'
            'window.__pyshadeTestkitBooted = true;\n'
            f'{bundle}\n'
            f'window.__pyshadeTestkit.run({run_config});'
            '})();'
        )

    def _injector(self) -> None:
        from pytauri import Manager

        inject_js = self._inject_source()
        start = time.monotonic()
        while not self.collector.hello.wait(timeout=2.0):
            if time.monotonic() - start > self._config.hello_timeout:
                self.collector.add_python_case(
                    CaseResult(
                        id='harness.hello_timeout',
                        status='error',
                        source='python',
                        detail={
                            'hint': "eval 未执行(注入失败)/前端资产未加载/IPC 被 capability 拒绝",
                            'timeout_s': self._config.hello_timeout,
                        },
                    )
                )
                self._app_handle.exit(1)
                return
            window = Manager.get_webview_window(self._app_handle, self._config.window_label)
            if window is not None:
                try:
                    title = window.title()
                    if title.startswith('PYSHADE_TESTKIT_ERROR'):
                        l.warning("pyshade.testing: 页面侧 runner 报错: {}", title)
                    window.eval(inject_js)
                except Exception as exc:
                    l.warning("pyshade.testing: eval 注入失败,重试中: {}", exc)

    def _watcher(self) -> None:
        if not self.collector.hello.wait(self._config.hello_timeout + 5.0):
            return  # injector 已处理超时退出
        if not self.collector.report.wait(self._config.total_timeout):
            self.collector.add_python_case(
                CaseResult(
                    id='harness.report_timeout',
                    status='error',
                    source='python',
                    detail={'last_heartbeat': self.collector.last_heartbeat() or {}},
                )
            )
            self._app_handle.exit(1)
            return
        # report 已落袋:等 JS 触发 case 5 关窗;未触发则兜底正常退出
        if not self._close_requested.wait(_CLOSE_GRACE_S):
            self._app_handle.exit(0)

    def _observe_close_behavior(self) -> None:
        """窗口已关、portal 仍存活:观察 stream_slow handler 对已销毁 Channel 的 send 行为。"""
        time.sleep(_OBSERVE_AFTER_CLOSE_S)
        relevant = [m for m in self._captured_logs if 'pyshade.asgi' in m]
        if any('application error' in m or 'wire error' in m for m in relevant):
            behavior = 'channel.send raised after window destroyed; bridge aborted the stream'
        elif relevant:
            behavior = 'bridge logged warnings after close (see harness log)'
        else:
            behavior = 'silent: no bridge errors after window close'
        self.collector.add_python_case(
            CaseResult(
                id='window.close_midstream',
                status='pass',  # M0 验收 = 无崩溃/无死锁 + 行为被记录
                source='python',
                detail={'observed_behavior': behavior, 'process_stable': True},
            )
        )

    def _build_env(self) -> EnvInfo:
        ua = str(self.collector.hello_info.get('userAgent', ''))
        webview = next((part for part in ua.split() if part.startswith('Edg/')), '')
        try:
            pytauri_version = pkg_version('pytauri')
        except Exception:
            pytauri_version = 'unknown'
        return EnvInfo(
            os=platform.system().lower(),
            runner='github-actions' if environ.get('GITHUB_ACTIONS') == 'true' else 'local',
            webview=webview.replace('Edg/', 'WebView2/'),
            tauri_ipc=bool(self.collector.hello_info.get('tauri', False)),
            visibility=str(self.collector.hello_info.get('visibility', self._config.visibility)),
            python=platform.python_version(),
            pytauri=pytauri_version,
        )

    def run(self) -> TestReport:
        cls = type(self)
        if cls._ran:
            raise RuntimeError("NativeHarness 每进程只能 run 一次(tao EventLoop 限制)")
        cls._ran = True

        config = self._config
        mount_test_routes(self._app, self.collector, actions=self)

        sink_id = l.add(lambda message: self._captured_logs.append(str(message)), level='WARNING')
        started = time.monotonic()

        from pytauri import RunEvent
        from pytauri_wheel.lib import builder_factory, context_factory

        # frontendDist 必须是相对 src_tauri_dir 的路径:Windows 盘符绝对路径(C:/...)
        # 会被 Tauri 的 untagged FrontendDist 反序列化误判为 URL(scheme 'c:'),页面加载失败
        rel_dist = Path(os.path.relpath(config.frontend_dist.absolute(), config.src_tauri_dir.absolute())).as_posix()
        tauri_config: dict[str, Any] = {
            'build': {'frontendDist': rel_dist},
            'app': {'windows': [self._window_config()]},
        }

        try:
            with start_blocking_portal('asyncio') as portal:
                adapter = AsgiIpcAdapter(self._app, portal)
                with adapter.lifespan():
                    tauri_app = builder_factory().build(
                        context=context_factory(config.src_tauri_dir.absolute(), tauri_config=tauri_config),
                        invoke_handler=adapter.invoke_handler(),
                    )
                    self._app_handle = tauri_app.handle()

                    def on_event(handle: Any, event: Any) -> None:
                        if isinstance(event, RunEvent.Ready):
                            threading.Thread(target=self._injector, daemon=True).start()
                            threading.Thread(target=self._watcher, daemon=True).start()

                    tauri_app.run_return(on_event)

                    if self._close_requested.is_set():
                        self._observe_close_behavior()
        finally:
            l.remove(sink_id)

        report = TestReport(
            run_id=f'{time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())}-{uuid.uuid4().hex[:8]}',
            env=self._build_env(),
            duration_ms=(time.monotonic() - started) * 1000,
        )
        raw = self.collector.raw_report
        if raw is not None:
            report.cases.extend(CaseResult.model_validate(c) for c in raw.get('cases', []))
        elif not self.collector.python_cases:
            report.cases.append(
                CaseResult(id='harness.no_report', status='error', source='python', detail={'hint': "页面未回传报告"})
            )
        report.cases.extend(self.collector.python_cases)
        apply_thresholds(report, config.thresholds)

        report.write_json(config.report_dir / 'report.json')
        markdown = report.to_markdown()
        (config.report_dir / 'report.md').write_text(markdown, encoding='utf-8', newline='\n')
        summary_path = environ.get('GITHUB_STEP_SUMMARY')
        if summary_path:
            with open(summary_path, 'a', encoding='utf-8') as fh:
                fh.write(markdown)
        return report


def main() -> None:
    """python -m pyshade.testing:CLI 入口(参数指向 runtime 工厂与产物路径)。"""
    import argparse
    import importlib
    from pathlib import Path

    parser = argparse.ArgumentParser(prog='pyshade.testing', description='PyShade 真机 E2E harness')
    parser.add_argument('--runtime', required=True, help='FastAPI 工厂,如 login_form.runtime:build_runtime')
    parser.add_argument('--src-tauri-dir', required=True, help='Tauri.toml + capabilities 所在目录')
    parser.add_argument('--dist', required=True, help='前端 vite build 产物目录')
    parser.add_argument('--testkit', required=True, help='testkit.js 路径')
    parser.add_argument('--report-dir', default='reports/native')
    args = parser.parse_args()

    module_path, _, attr = args.runtime.rpartition(':')
    factory = getattr(importlib.import_module(module_path), attr)
    from typing import cast

    raw: object = factory()
    candidate = cast('object', raw[1]) if isinstance(raw, tuple) else raw
    if not isinstance(candidate, FastAPI):
        raise SystemExit(f"{args.runtime} 未返回 FastAPI 实例")
    fastapi_app = candidate

    config = HarnessConfig(
        src_tauri_dir=Path(args.src_tauri_dir),
        frontend_dist=Path(args.dist),
        testkit_bundle=Path(args.testkit),
        report_dir=Path(args.report_dir),
    )
    report = NativeHarness(fastapi_app, config).run()
    print(report.to_markdown())
    raise SystemExit(0 if report.ok else 1)
