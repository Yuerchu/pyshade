/** case 7:事件 RTT 分位数(bench_echo,warmup 10 + 100 次串行)。 */

import { invokeEvent } from "@/runtime/invoke";
import { makeCase, percentile, type CaseResult } from "../types";

const WARMUP = 10;
const SAMPLES = 100;

export async function suiteRtt(): Promise<CaseResult> {
  const result = makeCase("rtt.bench_echo");

  for (let i = 0; i < WARMUP; i++) {
    await invokeEvent("bench_echo", {});
  }

  const times: number[] = [];
  for (let i = 0; i < SAMPLES; i++) {
    const t0 = performance.now();
    await invokeEvent("bench_echo", {});
    times.push(performance.now() - t0);
  }

  result.metrics.p50_ms = Number(percentile(times, 50).toFixed(2));
  result.metrics.p95_ms = Number(percentile(times, 95).toFixed(2));
  result.metrics.max_ms = Number(Math.max(...times).toFixed(2));
  result.metrics.samples = SAMPLES;
  return result;
}
