/**
 * 服务端推送订阅(M1 Phase 4):GET /_shade/push SSE。
 *
 * 走 shadeFetch 统一入口——IPC 模式是一条常驻流式请求(Channel 帧 → ReadableStream),
 * dev HTTP 模式是普通 SSE。服务端订阅即先推全量快照,重连后 merge 幂等,无需序号。
 */

import { shadeFetch } from "@/ipc/shadeFetch";
import { isPatchesEnvelope, type Patch } from "./patches";

const INITIAL_RETRY_MS = 500;
const MAX_RETRY_MS = 10_000;

function feedEvent(rawEvent: string, onPatches: (patches: Patch[]) => void): void {
  for (const line of rawEvent.split("\n")) {
    if (!line.startsWith("data: ")) {
      continue;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(line.slice("data: ".length));
    } catch {
      console.warn("[pyshade] push 事件不是合法 JSON,已忽略:", line);
      continue;
    }
    if (isPatchesEnvelope(parsed) && parsed.patches.length > 0) {
      onPatches(parsed.patches);
    }
  }
}

/** 订阅服务端 patch 推送;返回取消函数(React effect cleanup 直接可用)。 */
export function subscribePatches(onPatches: (patches: Patch[]) => void): () => void {
  let cancelled = false;
  let retryMs = INITIAL_RETRY_MS;

  const consume = async (body: ReadableStream<Uint8Array>): Promise<void> => {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (cancelled) {
        void reader.cancel();
        return;
      }
      if (done) {
        return;
      }
      buffer += decoder.decode(value, { stream: true });
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        feedEvent(buffer.slice(0, boundary), onPatches);
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");
      }
      retryMs = INITIAL_RETRY_MS; // 有数据到达即视为链路健康
    }
  };

  const loop = async (): Promise<void> => {
    while (!cancelled) {
      try {
        const res = await shadeFetch("/_shade/push");
        if (!res.ok || res.body === null) {
          throw new Error(`push subscribe failed: ${res.status}`);
        }
        await consume(res.body);
      } catch (err) {
        if (!cancelled) {
          console.warn("[pyshade] push 连接断开,指数退避重连:", err);
        }
      }
      if (cancelled) {
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, retryMs));
      retryMs = Math.min(retryMs * 2, MAX_RETRY_MS);
    }
  };

  void loop();
  return () => {
    cancelled = true;
  };
}
