/**
 * 配色方案(M4 dark mode),真机 WebView 内验证三条定案:
 * ①toggle 按当前解析结果取反并落为显式选择(localStorage);
 * ②"system" 清键回到跟随系统,解析结果与 matchMedia 一致;
 * ③class 策略:documentElement 的 .dark 由 resolvedDark 驱动。
 * 结束后恢复 localStorage 与 class 原状,不污染生产 App。
 */

import { useContext } from "react";
import { createRoot } from "react-dom/client";
import { ShadeAppProvider } from "@/runtime/app";
import { SCHEME_STORAGE_KEY } from "@/runtime/scheme";
import { ShadeRuntimeContext, type ShadeRuntimeStore } from "@/runtime/store";
import { check, makeCase, type CaseResult } from "../types";

let store: ShadeRuntimeStore | null = null;

function StoreProbe() {
  store = useContext(ShadeRuntimeContext);
  return null;
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 30));
const hasDark = () => document.documentElement.classList.contains("dark");

export async function suiteColorScheme(): Promise<CaseResult> {
  const result = makeCase("theme.color_scheme");
  const container = document.createElement("div");
  container.style.display = "none";
  document.body.appendChild(container);
  const root = createRoot(container);
  const originalStored = localStorage.getItem(SCHEME_STORAGE_KEY);
  const originalDark = hasDark();

  try {
    localStorage.removeItem(SCHEME_STORAGE_KEY);
    root.render(
      <ShadeAppProvider initial="ProbeOnly" colorScheme="light">
        <StoreProbe />
      </ShadeAppProvider>,
    );
    await flush();
    check(result, "light_default_no_dark_class", !hasDark());
    check(result, "store_resolved_light", store?.resolvedDark === false);

    store?.setColorScheme("toggle");
    await flush();
    check(result, "toggle_adds_dark_class", hasDark());
    check(result, "toggle_persists_explicit", localStorage.getItem(SCHEME_STORAGE_KEY) === "dark");
    check(result, "store_resolved_dark", store?.resolvedDark === true);

    store?.setColorScheme("toggle");
    await flush();
    check(result, "toggle_back_to_light", !hasDark());
    check(result, "light_persisted", localStorage.getItem(SCHEME_STORAGE_KEY) === "light");

    store?.setColorScheme("system");
    await flush();
    const prefersDark = matchMedia("(prefers-color-scheme: dark)").matches;
    check(result, "system_clears_storage", localStorage.getItem(SCHEME_STORAGE_KEY) === null);
    check(result, "system_matches_media", hasDark() === prefersDark, `prefersDark=${prefersDark}`);
    result.detail.prefers_dark = prefersDark;
  } finally {
    root.unmount();
    container.remove();
    store = null;
    if (originalStored === null) {
      localStorage.removeItem(SCHEME_STORAGE_KEY);
    } else {
      localStorage.setItem(SCHEME_STORAGE_KEY, originalStored);
    }
    document.documentElement.classList.toggle("dark", originalDark);
  }
  return result;
}
