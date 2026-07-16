"""真机验证:每项一个断言用例(共享一次 harness run 的报告)。M0 七项 + M2 路由语义。"""

import pytest

from pyshade.testing import CaseResult, TestReport

pytestmark = pytest.mark.e2e_native


def _case(report: TestReport, case_id: str) -> CaseResult:
    case = next((c for c in report.cases if c.id == case_id), None)
    assert case is not None, f'用例 {case_id} 不在报告中;cases={[c.id for c in report.cases]}'
    return case


def test_headers_fidelity(native_report: TestReport) -> None:
    case = _case(native_report, 'headers.fidelity')
    assert case.status == 'pass', case.model_dump()


def test_streaming_race(native_report: TestReport) -> None:
    case = _case(native_report, 'streaming.race')
    assert case.status == 'pass', case.model_dump()


def test_payload_size(native_report: TestReport) -> None:
    case = _case(native_report, 'payload.size')
    assert case.status == 'pass', case.model_dump()


def test_empty_body_raw(native_report: TestReport) -> None:
    case = _case(native_report, 'body.empty_raw')
    assert case.status == 'pass', case.model_dump()


def test_window_close_midstream(native_report: TestReport) -> None:
    case = _case(native_report, 'window.close_midstream')
    assert case.status == 'pass', case.model_dump()
    assert case.detail.get('process_stable') is True


def test_typing_latency(native_report: TestReport) -> None:
    case = _case(native_report, 'typing.latency')
    assert case.status == 'pass', case.model_dump()


def test_rtt_bench_echo(native_report: TestReport) -> None:
    case = _case(native_report, 'rtt.bench_echo')
    assert case.status == 'pass', case.model_dump()


def test_routing_state(native_report: TestReport) -> None:
    """M2 Phase 5 切页语义:ClientVal 重置 / overrides 存活 / push 订阅不重连。"""
    case = _case(native_report, 'routing.state')
    assert case.status == 'pass', case.model_dump()


def test_routing_keep_alive(native_report: TestReport) -> None:
    """M3 keep-alive:访问过的页面保持挂载(display:none),本地状态跨切页存活。"""
    case = _case(native_report, 'routing.keep_alive')
    assert case.status == 'pass', case.model_dump()


def test_routing_deep_link(native_report: TestReport) -> None:
    """M3 深链:hash 覆盖初始页、navigate 写 hash、hashchange 反向驱动、无效 hash 忽略。"""
    case = _case(native_report, 'routing.deep_link')
    assert case.status == 'pass', case.model_dump()


def test_theme_color_scheme(native_report: TestReport) -> None:
    """M4 dark mode:toggle 落显式选择、system 清键跟随 matchMedia、.dark class 驱动。"""
    case = _case(native_report, 'theme.color_scheme')
    assert case.status == 'pass', case.model_dump()


def test_push_connection_lost(native_report: TestReport) -> None:
    """断连指示:push 断流 → 左下角徽标出现;重连成功 → 消失;取消后重连循环终止。"""
    case = _case(native_report, 'push.connection_lost')
    assert case.status == 'pass', case.model_dump()


def test_overall_verdict(native_report: TestReport) -> None:
    assert native_report.ok, native_report.to_markdown()
