/**
 * shadeFetch:fetch 风格的 ASGI over IPC 客户端(design.md §3.7)。
 *
 * pytauri 环境走进程内 IPC(plugin:pytauri|pyfunc + PSA1 封包 + Channel 流式);
 * 浏览器 dev 环境回退 window.fetch(经 vite proxy 到 DevHttpServer)。
 * 无 body 时恒发 Uint8Array(0)——undefined 会被 pytauri 判为 InvokeBody::Json 拒绝。
 */

import { Channel, invoke } from "@tauri-apps/api/core";
import { ASGI_COMMAND, decodeEnvelope, decodeFrame, parseReject } from "./wire";

export interface ShadeFetchInit {
  method?: string;
  headers?: Record<string, string>;
  body?: Uint8Array | string | object;
}

function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function encodeBody(body: ShadeFetchInit["body"], headers: Record<string, string>): Uint8Array {
  if (body === undefined || body === null) {
    return new Uint8Array(0);
  }
  if (body instanceof Uint8Array) {
    return body;
  }
  if (typeof body === "string") {
    return new TextEncoder().encode(body);
  }
  if (!("content-type" in headers)) {
    headers["content-type"] = "application/json";
  }
  return new TextEncoder().encode(JSON.stringify(body));
}

const NULL_BODY_STATUS = new Set([101, 204, 205, 304]);

function toResponse(status: number, headers: [string, string][], body: BodyInit | null): Response {
  return new Response(NULL_BODY_STATUS.has(status) ? null : body, {
    status,
    headers: new Headers(headers),
  });
}

async function ipcFetch(path: string, init: ShadeFetchInit): Promise<Response> {
  const method = (init.method ?? "GET").toUpperCase();
  const appHeaders: Record<string, string> = { ...(init.headers ?? {}) };
  const bodyBytes = encodeBody(init.body, appHeaders);

  const [rawPath, query = ""] = path.split("?", 2) as [string, string?];

  // Channel 先建、onmessage 先挂:帧可能早于 invoke promise resolve 抵达,必须缓冲
  const buffered: Uint8Array[] = [];
  let sink: ((data: Uint8Array) => void) | null = null;
  const channel = new Channel<ArrayBuffer | number[]>();
  channel.onmessage = (data) => {
    const bytes = data instanceof ArrayBuffer ? new Uint8Array(data) : new Uint8Array(data);
    if (sink) {
      sink(bytes);
    } else {
      buffered.push(bytes);
    }
  };

  const headers: Record<string, string> = {
    ...appHeaders,
    pyfunc: ASGI_COMMAND,
    "x-pyshade-method": method,
    "x-pyshade-path": encodeURI(rawPath),
    "x-pyshade-channel": channel.toJSON(),
  };
  if (query) {
    headers["x-pyshade-query"] = query;
  }

  let raw: ArrayBuffer;
  try {
    raw = await invoke<ArrayBuffer>("plugin:pytauri|pyfunc", bodyBytes, { headers });
  } catch (err) {
    throw parseReject(err);
  }

  const { head, body } = decodeEnvelope(new Uint8Array(raw));
  if (!head.stream) {
    return toResponse(head.status, head.headers, body.length > 0 ? (body as unknown as BodyInit) : null);
  }

  // 流式:envelope 只带头,后续帧经 Channel
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const feed = (bytes: Uint8Array): void => {
        const frame = decodeFrame(bytes);
        if (frame.kind === "body") {
          controller.enqueue(frame.chunk);
        } else if (frame.kind === "end") {
          controller.close();
          sink = () => undefined;
        } else {
          controller.error(new Error(`[pyshade] stream error ${frame.code}: ${frame.message}`));
          sink = () => undefined;
        }
      };
      for (const bytes of buffered) {
        feed(bytes);
      }
      buffered.length = 0;
      sink = feed;
    },
  });
  return toResponse(head.status, head.headers, stream);
}

async function httpFetch(path: string, init: ShadeFetchInit): Promise<Response> {
  const headers = { ...(init.headers ?? {}) };
  const body = init.body === undefined ? undefined : encodeBody(init.body, headers);
  return fetch(path, {
    method: init.method ?? "GET",
    headers,
    body: body as BodyInit | undefined,
  });
}

/**
 * demo mock 钩子(M4 文档站,design.md §3.10):静态托管无 Python 后端时,
 * 站点脚本可挂 window.__PYSHADE_MOCK__ 拦截 /_shade/*,返回 Response 即短路
 * (JSON envelope / SSE ReadableStream 均可,patches 全链路照常驱动);
 * 返回 undefined 则回落真实 fetch——未定义时行为与既往完全一致。
 */
export type ShadeMockHandler = (path: string, init: ShadeFetchInit) => Promise<Response | undefined>;

declare global {
  interface Window {
    __PYSHADE_MOCK__?: ShadeMockHandler;
  }
}

/** 统一入口:pytauri 环境走 IPC;浏览器先问 mock 钩子,未接管则走 HTTP。 */
export async function shadeFetch(path: string, init?: ShadeFetchInit): Promise<Response> {
  const resolved = init ?? {};
  if (isTauri()) {
    return ipcFetch(path, resolved);
  }
  const mock = window.__PYSHADE_MOCK__;
  if (mock !== undefined) {
    const handled = await mock(path, resolved);
    if (handled !== undefined) {
      return handled;
    }
  }
  return httpFetch(path, resolved);
}
