/**
 * testkit runner:eval 注入的自驱动测试套件(M1 计划 Part B)。
 * 独立 IIFE bundle(vite.testkit.config.ts),不进生产 bundle。
 * 回程只走自家 ASGI over IPC(shadeFetch)——测试执行本身即通道压测。
 */

import { shadeFetch } from "@/ipc/shadeFetch";
import { suiteEmptyBody } from "./suites/emptyBody";
import { suiteHeaders } from "./suites/headers";
import { suitePayload } from "./suites/payload";
import { suiteRouting } from "./suites/routing";
import { suiteRtt } from "./suites/rtt";
import { suiteSpaEachClick, suiteSpaNavigate } from "./suites/spa";
import { suiteStreaming } from "./suites/streaming";
import { runCloseWindowScenario } from "./suites/closeWindow";
import { suiteTyping } from "./suites/typing";
import { makeCase, type CaseResult, type RunConfig, type SuiteFn } from "./types";

const BUILTIN_SUITES: [string, SuiteFn][] = [
  ["headers.fidelity", suiteHeaders],
  ["streaming.race", suiteStreaming],
  ["payload.size", suitePayload],
  ["body.empty_raw", suiteEmptyBody],
  ["typing.latency", suiteTyping],
  ["rtt.bench_echo", suiteRtt],
  ["routing.state", suiteRouting],
  ["spa.each_click", suiteSpaEachClick],
  ["spa.navigate", suiteSpaNavigate],
];

const extraSuites: [string, SuiteFn][] = [];

async function post(path: string, payload: unknown): Promise<void> {
  await shadeFetch(path, { method: "POST", body: payload as object });
}

function envInfo(): Record<string, unknown> {
  return {
    userAgent: navigator.userAgent,
    visibility: document.visibilityState,
    tauri: "__TAURI_INTERNALS__" in window,
    protocol: location.protocol,
  };
}

let currentCase = "(init)";

declare global {
  interface Window {
    __pyshadeTestkitBooted?: boolean;
  }
}

async function run(config: RunConfig): Promise<void> {
  try {
    await runInner(config);
  } catch (err) {
    // 错误写入 title 供 harness 经 WebviewWindow.title() 读取诊断;
    // 清 guard 标志允许下一轮 eval 重试(页面可能尚未就绪)
    document.title = `PYSHADE_TESTKIT_ERROR: ${String(err)}`.slice(0, 200);
    window.__pyshadeTestkitBooted = false;
    console.error("[pyshade testkit]", err);
  }
}

async function runInner(config: RunConfig): Promise<void> {
  await post("/_shade/_test/hello", envInfo());

  const heartbeat = setInterval(() => {
    void post("/_shade/_test/heartbeat", { case: currentCase, at: Date.now() });
  }, 1000);

  const selected = config.suites;
  const suites = [...BUILTIN_SUITES, ...extraSuites].filter(
    ([id]) => !selected || selected.includes(id),
  );

  const cases: CaseResult[] = [];
  for (const [id, fn] of suites) {
    currentCase = id;
    try {
      cases.push(await fn(config));
    } catch (err) {
      const result = makeCase(id);
      result.status = "error";
      result.detail.error = String(err);
      cases.push(result);
    }
  }

  clearInterval(heartbeat);
  currentCase = "(report)";
  await post("/_shade/_test/report", { cases, env: envInfo() });

  // case 5:必须在 report 落袋之后(关窗后一切回传失效)
  if (!selected || selected.includes("window.close_midstream")) {
    currentCase = "window.close_midstream";
    await runCloseWindowScenario();
  }
}

function register(id: string, fn: SuiteFn): void {
  extraSuites.push([id, fn]);
}

declare global {
  interface Window {
    __pyshadeTestkit?: { run: (config: RunConfig) => void; register: (id: string, fn: SuiteFn) => void };
  }
}

window.__pyshadeTestkit = {
  run: (config: RunConfig) => {
    void run(config);
  },
  register,
};
