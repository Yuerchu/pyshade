"""测试路由与报告模型的单测(httpx ASGITransport,零 pytauri 依赖)。"""

import hashlib

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from pyshade.testing import (
    CaseResult,
    HarnessConfig,
    ReportCollector,
    TestReport,
    apply_thresholds,
    mount_test_routes,
    percentile,
)

pytestmark = pytest.mark.anyio


class FakeActions:
    def __init__(self) -> None:
        self.closed = 0

    def close_window(self) -> None:
        self.closed += 1


def _build(actions: FakeActions | None = None) -> tuple[httpx.AsyncClient, ReportCollector]:
    app = FastAPI()
    collector = ReportCollector()
    mount_test_routes(app, collector, actions=actions)
    transport = ASGITransport(app=app)  # pyright: ignore[reportArgumentType]
    return httpx.AsyncClient(transport=transport, base_url='http://t'), collector


async def test_hello_sets_event() -> None:
    client, collector = _build()
    async with client:
        resp = await client.post('/_shade/_test/hello', json={'visibility': 'visible', 'tauri': True})
    assert resp.status_code == 200
    assert collector.hello.is_set()
    assert collector.hello_info['visibility'] == 'visible'


async def test_report_sets_event() -> None:
    client, collector = _build()
    async with client:
        await client.post('/_shade/_test/report', json={'cases': []})
    assert collector.report.is_set()
    assert collector.raw_report == {'cases': []}


async def test_heartbeat_recorded() -> None:
    client, collector = _build()
    async with client:
        await client.post('/_shade/_test/heartbeat', json={'case': 'rtt', 'step': 3})
    assert collector.last_heartbeat() == {'case': 'rtt', 'step': 3}


async def test_echo_roundtrip() -> None:
    client, _ = _build()
    long_path = 'x' * 2048
    body = b'\x00\x01payload'
    async with client:
        resp = await client.post(f'/_shade/_test/echo/{long_path}?a=1&b=2', content=body)
    data = resp.json()
    assert data['path'].endswith(long_path)
    assert data['query'] == 'a=1&b=2'
    assert data['body_len'] == len(body)
    assert data['body_sha256'] == hashlib.sha256(body).hexdigest()


async def test_blob_deterministic_pattern() -> None:
    client, _ = _build()
    async with client:
        resp = await client.get('/_shade/_test/blob', params={'size': 1000})
    content = resp.content
    assert len(content) == 1000
    assert content[:256] == bytes(range(256))


async def test_sink() -> None:
    client, _ = _build()
    payload = bytes(range(256)) * 4
    async with client:
        resp = await client.post('/_shade/_test/sink', content=payload)
    assert resp.json() == {'len': 1024, 'sha256': hashlib.sha256(payload).hexdigest()}


async def test_stream_fast_frame_sequence() -> None:
    client, _ = _build()
    async with client:
        resp = await client.get('/_shade/_test/stream_fast', params={'frames': 5})
    content = resp.content
    # 每帧 6 位序号 + ':' + 64 填充字节
    assert content[:7] == b'000000:'
    assert len(content) == 5 * (7 + 64)


async def test_close_window_calls_actions() -> None:
    actions = FakeActions()
    client, _ = _build(actions)
    async with client:
        await client.post('/_shade/_test/close_window')
    assert actions.closed == 1


class TestReportModel:
    def test_percentile(self) -> None:
        values = [float(i) for i in range(1, 101)]
        assert percentile(values, 50) == 50.0
        assert percentile(values, 95) == 95.0
        assert percentile([], 50) == 0.0

    def test_thresholds_upper_and_lower(self) -> None:
        report = TestReport(
            cases=[
                CaseResult(id='rtt.bench_echo', metrics={'p50_ms': 1.8, 'p95_ms': 4.2}),
                CaseResult(id='headers.fidelity', metrics={'max_ok_kb': 64}),
            ]
        )
        apply_thresholds(report, {'rtt.p50_ms': 5, 'rtt.p95_ms': 20, 'headers.max_ok_kb_min': 8})
        assert report.verdict == 'pass'
        assert report.cases[0].thresholds['rtt.p50_ms'].ok

    def test_threshold_failure(self) -> None:
        report = TestReport(cases=[CaseResult(id='rtt.bench_echo', metrics={'p50_ms': 9.0})])
        apply_thresholds(report, {'rtt.p50_ms': 5})
        assert report.verdict == 'fail'
        assert report.cases[0].status == 'fail'

    def test_missing_metric_is_error(self) -> None:
        report = TestReport(cases=[CaseResult(id='rtt.bench_echo', metrics={})])
        apply_thresholds(report, {'rtt.p50_ms': 5})
        assert report.verdict == 'error'

    def test_markdown_contains_verdict(self) -> None:
        report = TestReport(
            cases=[CaseResult(id='rtt.bench_echo', metrics={'p50_ms': 1.8, 'p95_ms': 4.0, 'max_ms': 9.0})]
        )
        apply_thresholds(report, {'rtt.p50_ms': 5})
        md = report.to_markdown()
        assert '1/1 pass' in md
        assert 'design.md §4 回填数据' in md

    def test_json_schema_alias(self) -> None:
        report = TestReport()
        dumped = report.model_dump(by_alias=True)
        assert dumped['schema'] == 'pyshade-native-report/1'

    def test_default_config_paths(self, tmp_path: object) -> None:
        from pathlib import Path

        config = HarnessConfig(src_tauri_dir=Path('a'), frontend_dist=Path('b'), testkit_bundle=Path('c'))
        assert config.visibility == 'hidden'
        assert config.thresholds['rtt.p50_ms'] == 5
