"""测试报告模型与产出:JSON(机器)+ Markdown(GitHub step summary)。"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


def percentile(values: Sequence[float], q: float) -> float:
    """最近秩法分位数;空序列返回 0。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q / 100 * len(ordered)) - 1))
    return ordered[index]


class Assertion(BaseModel):
    name: str
    ok: bool
    detail: str = ''


class ThresholdResult(BaseModel):
    limit: float
    actual: float
    ok: bool


class CaseResult(BaseModel):
    id: str
    status: Literal['pass', 'fail', 'error', 'skip'] = 'pass'
    source: Literal['js', 'python'] = 'js'
    assertions: list[Assertion] = []
    metrics: dict[str, float] = {}
    thresholds: dict[str, ThresholdResult] = {}
    warnings: list[str] = []
    detail: dict[str, Any] = {}


class EnvInfo(BaseModel):
    os: str = ''
    runner: str = ''
    webview: str = ''
    tauri_ipc: bool = False
    visibility: str = ''
    python: str = ''
    pytauri: str = ''


class TestReport(BaseModel):
    __test__ = False  # 名字带 Test 前缀,阻止 pytest 收集

    schema_id: str = Field(default='pyshade-native-report/1', serialization_alias='schema')
    run_id: str = ''
    env: EnvInfo = EnvInfo()
    duration_ms: float = 0
    verdict: Literal['pass', 'fail', 'error'] = 'error'
    cases: list[CaseResult] = []

    @property
    def ok(self) -> bool:
        return self.verdict == 'pass'

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(by_alias=True), indent=2, ensure_ascii=False) + '\n',
            encoding='utf-8',
            newline='\n',
        )

    def to_markdown(self) -> str:
        icon = {'pass': '✅', 'fail': '❌', 'error': '💥', 'skip': '⏭️'}
        passed = sum(1 for c in self.cases if c.status == 'pass')
        lines = [
            f"## PyShade 真机验证 — {self.env.os} / {self.env.webview or 'WebView?'}",
            '',
            f"**Verdict: {icon.get(self.verdict, '?')} {passed}/{len(self.cases)} pass** "
            f"({self.duration_ms / 1000:.1f}s, window: {self.env.visibility})",
            '',
            '| Case | Status | 关键指标 | 验收线 |',
            '|---|---|---|---|',
        ]
        for case in self.cases:
            metrics = ', '.join(f'{k}={v:g}' for k, v in sorted(case.metrics.items())) or '—'
            limits = (
                ', '.join(
                    f'{key.rsplit(".", 1)[-1]}{"≥" if key.endswith("_min") else "≤"}{t.limit:g}'
                    for key, t in sorted(case.thresholds.items())
                )
                or '—'
            )
            lines.append(f'| {case.id} | {icon.get(case.status, "?")} | {metrics} | {limits} |')
        rtt = next((c for c in self.cases if c.id.startswith('rtt.')), None)
        if rtt and rtt.metrics:
            lines += [
                '',
                '### design.md §4 回填数据',
                f"进程内 IPC RTT: p50={rtt.metrics.get('p50_ms', 0):g}ms "
                f"p95={rtt.metrics.get('p95_ms', 0):g}ms max={rtt.metrics.get('max_ms', 0):g}ms "
                f"(n={rtt.metrics.get('samples', 0):g})",
            ]
        return '\n'.join(lines) + '\n'


def apply_thresholds(report: TestReport, thresholds: dict[str, float]) -> None:
    """按 '{case前缀}.{metric}[_min]' 键对 case metrics 求值,写入 thresholds 并更新 verdict。"""
    for key, limit in thresholds.items():
        case_prefix, metric_expr = key.split('.', 1)
        lower_bound = metric_expr.endswith('_min')
        metric = metric_expr[: -len('_min')] if lower_bound else metric_expr
        case = next((c for c in report.cases if c.id.split('.')[0] == case_prefix), None)
        if case is None or case.status == 'skip':
            continue
        actual = case.metrics.get(metric)
        if actual is None:
            case.status = 'error'
            case.warnings.append(f"验收线 {key} 需要 metric '{metric}',但用例未上报")
            continue
        ok = actual >= limit if lower_bound else actual <= limit
        case.thresholds[key] = ThresholdResult(limit=limit, actual=actual, ok=ok)
        if not ok and case.status == 'pass':
            case.status = 'fail'

    if any(c.status == 'error' for c in report.cases):
        report.verdict = 'error'
    elif all(c.status in ('pass', 'skip') for c in report.cases) and report.cases:
        report.verdict = 'pass'
    else:
        report.verdict = 'fail'
