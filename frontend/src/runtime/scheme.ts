/**
 * 配色方案(M4 dark mode,design.md §3.11):color scheme 归客户端所有(route 先例)。
 * class 策略:documentElement 挂 `.dark`;localStorage 只存显式选择("system" 清键回到跟随系统)。
 * 独立文件:app.tsx(Provider 状态机)与 page.ts(无 Provider 回落)共用,避免环形依赖。
 */

export type ColorSchemeMode = "system" | "light" | "dark";

export const SCHEME_STORAGE_KEY = "pyshade:color-scheme";

export function readStoredScheme(): "light" | "dark" | null {
  try {
    const raw = localStorage.getItem(SCHEME_STORAGE_KEY);
    return raw === "light" || raw === "dark" ? raw : null;
  } catch {
    return null; // localStorage 不可用(隐私模式等)时回落默认
  }
}

export function persistScheme(mode: ColorSchemeMode): void {
  try {
    if (mode === "system") {
      localStorage.removeItem(SCHEME_STORAGE_KEY);
    } else {
      localStorage.setItem(SCHEME_STORAGE_KEY, mode);
    }
  } catch {
    // 不可持久化时静默:本次会话内仍生效
  }
}

export function systemPrefersDark(): boolean {
  return typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches;
}

export function resolveDark(mode: ColorSchemeMode): boolean {
  return mode === "dark" || (mode === "system" && systemPrefersDark());
}

export function applySchemeClass(dark: boolean): void {
  document.documentElement.classList.toggle("dark", dark);
}
