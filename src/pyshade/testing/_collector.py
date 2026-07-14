"""结果收集器:hello/heartbeat/report 三事件 + Python 侧观察 case。

事件用 threading.Event:置位发生在 portal loop(路由 handler),
等待发生在 harness 主线程,threading.Event 的 set/wait 跨线程安全。
"""

import threading
from typing import Any

from pyshade.testing._report import CaseResult


class ReportCollector:
    def __init__(self) -> None:
        self.hello = threading.Event()
        self.report = threading.Event()
        self.hello_info: dict[str, Any] = {}
        self.raw_report: dict[str, Any] | None = None
        self._heartbeats: list[dict[str, Any]] = []
        self._python_cases: list[CaseResult] = []
        self._lock = threading.Lock()

    def on_hello(self, info: dict[str, Any]) -> None:
        with self._lock:
            self.hello_info.update(info)
        self.hello.set()

    def on_heartbeat(self, beat: dict[str, Any]) -> None:
        with self._lock:
            self._heartbeats.append(beat)

    def on_report(self, data: dict[str, Any]) -> None:
        with self._lock:
            self.raw_report = data
        self.report.set()

    def add_python_case(self, case: CaseResult) -> None:
        with self._lock:
            self._python_cases.append(case)

    @property
    def python_cases(self) -> list[CaseResult]:
        with self._lock:
            return list(self._python_cases)

    def last_heartbeat(self) -> dict[str, Any] | None:
        with self._lock:
            return self._heartbeats[-1] if self._heartbeats else None
