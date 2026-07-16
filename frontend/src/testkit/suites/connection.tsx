/**
 * Connection Lost 指示(发版前审查加固):push 订阅断流时 App Provider 在左下角渲染
 * `#pyshade-connection-lost` 徽标,重连成功即消失;无 push 订阅的 Provider 永不渲染。
 * 用注入的 fake transport 仿真:健康流 → 断流(重连挂起)→ 恢复;结束断言取消后
 * 重连循环真正终止(fetch 计数不再增长)。
 */

import { useContext } from "react";
import { createRoot } from "react-dom/client";
import { ShadeAppProvider } from "@/runtime/app";
import { ShadeRuntimeContext, type ShadeRuntimeStore } from "@/runtime/store";
import { check, makeCase, type CaseResult } from "../types";

let store: ShadeRuntimeStore | null = null;
// 经函数读取:defeat TS 对 `store = null` 之后读取的控制流收窄(render 回调会重新赋值)
const currentStore = (): ShadeRuntimeStore | null => store;

function StoreProbe() {
  store = useContext(ShadeRuntimeContext);
  return null;
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const badge = () => document.getElementById("pyshade-connection-lost");

async function waitFor(predicate: () => boolean, timeoutMs: number): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (predicate()) {
      return true;
    }
    await sleep(25);
  }
  return predicate();
}

interface FakeTransport {
  fetchImpl: (path: string) => Promise<Response>;
  breakStream: () => void;
  restore: () => void;
  callCount: () => number;
}

function makeFakeTransport(): FakeTransport {
  let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
  let calls = 0;
  let restored = false;

  const makeStreamResponse = (): Response => {
    const stream = new ReadableStream<Uint8Array>({
      start(c) {
        controller = c;
        c.enqueue(new TextEncoder().encode('data: {"patches": []}\n\n'));
      },
    });
    return new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } });
  };

  return {
    fetchImpl: (_path: string) => {
      calls += 1;
      if (calls === 1 || restored) {
        return Promise.resolve(makeStreamResponse());
      }
      // 断连期:重连请求挂起(永不 resolve),保持 disconnected 状态
      return new Promise<Response>(() => undefined);
    },
    breakStream: () => {
      controller?.close();
      controller = null;
    },
    restore: () => {
      restored = true;
    },
    callCount: () => calls,
  };
}

export async function suitePushConnectionLost(): Promise<CaseResult> {
  const result = makeCase("push.connection_lost");
  const container = document.createElement("div");
  container.style.display = "none";
  document.body.appendChild(container);
  const root = createRoot(container);
  const transport = makeFakeTransport();

  try {
    root.render(
      <ShadeAppProvider initial="ProbeOnly" push pushFetch={transport.fetchImpl}>
        <StoreProbe />
      </ShadeAppProvider>,
    );
    await waitFor(() => transport.callCount() >= 1, 2000);
    await sleep(50);
    check(result, "connected_no_badge", badge() === null);
    check(result, "store_not_lost", store?.connectionLost === false);

    transport.breakStream();
    const appeared = await waitFor(() => badge() !== null, 3000);
    check(result, "badge_appears_on_break", appeared);
    check(result, "badge_text", badge()?.textContent?.includes("Connection lost") === true);
    check(result, "store_lost", store?.connectionLost === true);

    transport.restore();
    transport.breakStream(); // 无害:controller 已清空
    // 下一轮退避重连(500ms 起步)拿到健康流后徽标消失
    const recovered = await waitFor(() => badge() === null, 5000);
    check(result, "badge_gone_on_reconnect", recovered);
    check(result, "store_recovered", store?.connectionLost === false);
  } finally {
    root.unmount();
    container.remove();
    store = null;
  }

  // 取消后重连循环必须终止:等一个退避周期,fetch 计数不再增长
  const callsAfterUnmount = transport.callCount();
  await sleep(700);
  check(result, "no_fetch_after_cancel", transport.callCount() === callsAfterUnmount);

  // 无 push 的 Provider 对照:永不渲染徽标
  const plainContainer = document.createElement("div");
  plainContainer.style.display = "none";
  document.body.appendChild(plainContainer);
  const plainRoot = createRoot(plainContainer);
  try {
    plainRoot.render(
      <ShadeAppProvider initial="ProbeOnly">
        <StoreProbe />
      </ShadeAppProvider>,
    );
    await sleep(50);
    check(result, "no_push_no_badge", badge() === null);
    check(result, "no_push_store_false", currentStore()?.connectionLost === false);
  } finally {
    plainRoot.unmount();
    plainContainer.remove();
    store = null;
  }
  return result;
}
