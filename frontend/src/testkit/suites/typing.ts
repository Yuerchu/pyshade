/**
 * case 6:受控输入键入延迟 + 0-IPC 证明。
 *
 * 不用 PerformanceObserver:Event Timing 只记 isTrusted 事件,合成事件不入账;
 * 隐藏窗口 rAF 挂起。改用双指标:sync_ms(dispatch 同步耗时,含 React onChange+re-render)
 * 与 fence_ms(dispatch 起点到 setTimeout(0) 回调,含微任务/effect flush)。
 */

import { check, makeCase, percentile, type CaseResult } from "../types";

const TARGET_ID = "LoginPage.username";
const CHARS = 30;

function nextTick(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

export async function suiteTyping(): Promise<CaseResult> {
  const result = makeCase("typing.latency");
  const el = document.getElementById(TARGET_ID) as HTMLInputElement | null;
  if (el === null) {
    result.status = "error";
    result.detail.error = `element #${TARGET_ID} not found`;
    return result;
  }

  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  if (!setter) {
    result.status = "error";
    result.detail.error = "HTMLInputElement value setter unavailable";
    return result;
  }

  const ipcBefore = window.__PYSHADE_IPC_COUNT__ ?? 0;
  el.focus();

  const syncTimes: number[] = [];
  const fenceTimes: number[] = [];
  for (let i = 0; i < CHARS; i++) {
    const ch = String.fromCharCode(97 + (i % 26));
    const t0 = performance.now();
    el.dispatchEvent(new KeyboardEvent("keydown", { key: ch, bubbles: true }));
    setter.call(el, el.value + ch);
    el.dispatchEvent(new InputEvent("input", { bubbles: true }));
    el.dispatchEvent(new KeyboardEvent("keyup", { key: ch, bubbles: true }));
    syncTimes.push(performance.now() - t0);
    await nextTick();
    fenceTimes.push(performance.now() - t0);
  }

  const duringDelta = (window.__PYSHADE_IPC_COUNT__ ?? 0) - ipcBefore;
  check(result, "zero_ipc_while_typing", duringDelta === 0, `delta=${duringDelta}`);

  // blur 触发 React onBlur → on_change 事件恰一次
  el.blur();
  const blurDeadline = performance.now() + 2000;
  let blurDelta = 0;
  while (performance.now() < blurDeadline) {
    blurDelta = (window.__PYSHADE_IPC_COUNT__ ?? 0) - ipcBefore;
    if (blurDelta >= 1) break;
    await nextTick();
  }
  check(result, "blur_fires_exactly_once", blurDelta === 1, `delta=${blurDelta}`);

  result.metrics.sync_p50_ms = Number(percentile(syncTimes, 50).toFixed(2));
  result.metrics.sync_p95_ms = Number(percentile(syncTimes, 95).toFixed(2));
  result.metrics.fence_p50_ms = Number(percentile(fenceTimes, 50).toFixed(2));
  result.metrics.fence_p95_ms = Number(percentile(fenceTimes, 95).toFixed(2));
  return result;
}
