/**
 * 路由状态语义(M2 Phase 5),真机 WebView 内验证三条定案:
 * ①切页 ClientVal(useState)重置——unmount 即丢;
 * ②overrides 跨页存活——服务端 Update 不因切页蒸发(App 级共享 store);
 * ③push 订阅不随切页重连(App 层订阅,计数器见 runtime/push.ts)。
 * 独立 createRoot 渲染进隐藏容器,与生产 App 树互不干扰,结束后 unmount 释放订阅。
 */

import { useContext, useState } from "react";
import { createRoot } from "react-dom/client";
import { ShadeAppProvider, ShadeRouter } from "@/runtime/app";
import { ShadeRuntimeContext, type ShadeRuntimeStore } from "@/runtime/store";
import { usePageRuntime } from "@/runtime/page";
import { check, makeCase, type CaseResult } from "../types";

let store: ShadeRuntimeStore | null = null;

function StoreProbe() {
  store = useContext(ShadeRuntimeContext);
  return null;
}

function RouteHome() {
  const rt = usePageRuntime();
  const [count, setCount] = useState(0);
  return (
    <div>
      <span id="pyshade-routing-count">{count}</span>
      <span id="pyshade-routing-label">{rt.ov("RouteHome.label", "text", "初始")}</span>
      <button id="pyshade-routing-inc" onClick={() => setCount((c) => c + 1)} />
      <button id="pyshade-routing-goto" onClick={() => rt.navigate("RouteDetail")} />
    </div>
  );
}

function RouteDetail() {
  usePageRuntime();
  return <div id="pyshade-routing-detail" />;
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 30));

function textOf(container: HTMLElement, id: string): string | null {
  return container.querySelector(`#${id}`)?.textContent ?? null;
}

export async function suiteRouting(): Promise<CaseResult> {
  const result = makeCase("routing.state");
  const container = document.createElement("div");
  container.style.display = "none";
  document.body.appendChild(container);
  const root = createRoot(container);
  const subsBefore = window.__PYSHADE_PUSH_SUBSCRIBE_COUNT__ ?? 0;

  try {
    root.render(
      <ShadeAppProvider initial="RouteHome" push>
        <StoreProbe />
        <ShadeRouter pages={{ RouteHome, RouteDetail }} />
      </ShadeAppProvider>,
    );
    await flush();
    check(result, "initial_mount", textOf(container, "pyshade-routing-count") === "0");
    const subsMounted = window.__PYSHADE_PUSH_SUBSCRIBE_COUNT__ ?? 0;
    check(result, "push_subscribed_once", subsMounted === subsBefore + 1, `delta=${subsMounted - subsBefore}`);

    // 页面本地状态(ClientVal 语义)自增 + 服务端 patch 落进共享 store
    container.querySelector<HTMLButtonElement>("#pyshade-routing-inc")?.click();
    container.querySelector<HTMLButtonElement>("#pyshade-routing-inc")?.click();
    store?.applyPatches([{ target: "RouteHome.label", props: { text: "补丁" } }]);
    await flush();
    check(result, "client_state_incremented", textOf(container, "pyshade-routing-count") === "2");
    check(result, "override_applied", textOf(container, "pyshade-routing-label") === "补丁");

    // rt.navigate 切页:RouteDetail 挂载,RouteHome 卸载
    container.querySelector<HTMLButtonElement>("#pyshade-routing-goto")?.click();
    await flush();
    check(result, "detail_mounted", container.querySelector("#pyshade-routing-detail") !== null);
    check(result, "home_unmounted", container.querySelector("#pyshade-routing-count") === null);

    // $nav patch 走服务端导航同款路径切回
    store?.applyPatches([{ target: "$nav", props: { page: "RouteHome" } }]);
    await flush();
    check(result, "client_state_reset", textOf(container, "pyshade-routing-count") === "0");
    check(result, "override_survives_navigation", textOf(container, "pyshade-routing-label") === "补丁");

    const subsAfter = window.__PYSHADE_PUSH_SUBSCRIBE_COUNT__ ?? 0;
    check(result, "push_not_resubscribed", subsAfter === subsMounted, `delta=${subsAfter - subsMounted}`);
    result.detail.subscribe_count = subsAfter - subsBefore;
  } finally {
    root.unmount();
    container.remove();
    store = null;
  }
  return result;
}
