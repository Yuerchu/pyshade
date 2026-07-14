/**
 * case 5:窗口关闭时半途请求的 Channel 行为(Python 侧观察,本文件只负责触发)。
 * 必须在 report 落袋之后执行——关窗后一切回传失效。
 */

import { shadeFetch } from "@/ipc/shadeFetch";

export async function runCloseWindowScenario(): Promise<void> {
  const res = await shadeFetch("/_shade/_test/stream_slow?frames=100&delay_ms=100");
  const reader = res.body?.getReader();
  if (reader) {
    for (let i = 0; i < 3; i++) {
      await reader.read();
    }
  }
  // fire-and-forget:Python 侧收到后关窗,本请求的响应不再送达
  void shadeFetch("/_shade/_test/close_window", { method: "POST" });
}
