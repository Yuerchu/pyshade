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

declare global {
  interface Window {
    /** subscribePatches 调用计数(重连不计):testkit 断言切页不重订阅。 */
    __PYSHADE_PUSH_SUBSCRIBE_COUNT__?: number;
  }
}

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

export type PushStatus = "connected" | "disconnected";

export interface SubscribeOptions {
  /** 连接状态变化回调(去重:仅状态翻转时触发;首次连接失败也触发;取消后不再触发)。 */
  onStatus?: (status: PushStatus) => void;
  /** 传输层注入口(默认 shadeFetch);testkit 断流仿真用,生成代码恒不传。 */
  fetchImpl?: (path: string) => Promise<Response>;
}

/** 订阅服务端 patch 推送;返回取消函数(React effect cleanup 直接可用)。
 *
 * 取消对 idle 流同样生效:挂起的 reader.read() 被 reader.cancel() 打断(HTTP 模式
 * 即中止 fetch、释放服务端订阅席位),退避等待被立即唤醒后循环退出。
 */
export function subscribePatches(onPatches: (patches: Patch[]) => void, options?: SubscribeOptions): () => void {
  if (typeof window !== "undefined") {
    window.__PYSHADE_PUSH_SUBSCRIBE_COUNT__ = (window.__PYSHADE_PUSH_SUBSCRIBE_COUNT__ ?? 0) + 1;
  }
  const fetchImpl = options?.fetchImpl ?? shadeFetch;
  let cancelled = false;
  let retryMs = INITIAL_RETRY_MS;
  let activeReader: ReadableStreamDefaultReader<Uint8Array> | null = null;
  let wakeRetry: (() => void) | null = null;
  let lastStatus: PushStatus | null = null;

  const emitStatus = (status: PushStatus): void => {
    if (cancelled || status === lastStatus) {
      return;
    }
    lastStatus = status;
    options?.onStatus?.(status);
  };

  const consume = async (body: ReadableStream<Uint8Array>): Promise<void> => {
    const reader = body.getReader();
    activeReader = reader;
    try {
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (cancelled) {
          void reader.cancel().catch(() => undefined);
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
    } finally {
      activeReader = null;
    }
  };

  const loop = async (): Promise<void> => {
    while (!cancelled) {
      try {
        const res = await fetchImpl("/_shade/push");
        if (!res.ok || res.body === null) {
          throw new Error(`push subscribe failed: ${res.status}`);
        }
        emitStatus("connected");
        await consume(res.body);
      } catch (err) {
        if (!cancelled) {
          console.warn("[pyshade] push 连接断开,指数退避重连:", err);
        }
      }
      if (cancelled) {
        return;
      }
      emitStatus("disconnected");
      await new Promise<void>((resolve) => {
        wakeRetry = resolve;
        setTimeout(resolve, retryMs);
      });
      wakeRetry = null;
      retryMs = Math.min(retryMs * 2, MAX_RETRY_MS);
    }
  };

  void loop();
  return () => {
    cancelled = true;
    void activeReader?.cancel().catch(() => undefined);
    wakeRetry?.();
  };
}
