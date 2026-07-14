"""HarnessConfig:自驱动 E2E harness 的纯数据配置。"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

DEFAULT_THRESHOLDS: dict[str, float] = {
    # 键格式 '{case前缀}.{metric}';'_min' 后缀表示下限(actual >= limit),否则上限
    'headers.max_ok_kb_min': 8,
    'payload.max_ok_mb_min': 8,
    'typing.fence_p95_ms': 50,
    'rtt.p50_ms': 5,
    'rtt.p95_ms': 20,
}


@dataclass(frozen=True)
class HarnessConfig:
    """NativeHarness 配置;visibility 是 R1/R2 风险的应对开关。"""

    src_tauri_dir: Path
    frontend_dist: Path
    testkit_bundle: Path
    window_label: str = 'main'
    visibility: Literal['hidden', 'offscreen', 'visible'] = 'hidden'
    run_config: dict[str, Any] = field(default_factory=dict[str, Any])
    thresholds: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    hello_timeout: float = 20.0
    total_timeout: float = 300.0
    report_dir: Path = Path('reports/native')
