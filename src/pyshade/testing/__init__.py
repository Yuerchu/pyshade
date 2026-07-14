"""pyshade.testing:自驱动真机 E2E harness(M1 计划 Part B)。

启动隐藏窗口的 pytauri 应用 → eval 注入 testkit bundle → 页面内执行测试
(合成事件/测量/shadeFetch)→ 结果经自家 ASGI over IPC 回传 → Python 断言并产出报告。
用户可用同一 harness 测试自己的 PyShade 应用。
"""

from pyshade.testing._collector import ReportCollector
from pyshade.testing._config import DEFAULT_THRESHOLDS, HarnessConfig
from pyshade.testing._report import (
    Assertion,
    CaseResult,
    EnvInfo,
    TestReport,
    apply_thresholds,
    percentile,
)
from pyshade.testing._routes import HarnessActions, mount_test_routes

__all__ = [
    'DEFAULT_THRESHOLDS',
    'Assertion',
    'CaseResult',
    'EnvInfo',
    'HarnessActions',
    'HarnessConfig',
    'ReportCollector',
    'TestReport',
    'apply_thresholds',
    'mount_test_routes',
    'percentile',
]
