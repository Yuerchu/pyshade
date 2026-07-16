/**
 * App 级运行时骨架(M2 Phase 5 / M3 keep-alive 与深链):
 * app.gen.tsx 只聚合参数与页面表,骨架在此手写。
 *
 * - overrides 提升 App 级共享:服务端 Update 不因切页蒸发;
 * - push 订阅提升 App 层:切页不断连、他页停留时后台推送不丢;
 * - $nav 保留地址:服务端 Navigate 编码为 patch,在此拦截切页;
 * - 页面状态默认 unmount 即丢;Router keepAlive 时访问过的页面保持挂载(display:none),
 *   ClientVal/受控输入跨切页存活——跨页数据的正门仍是 ServerState;
 * - 深链:#/PageName hash 路由(deepLink 默认 false:testkit 双 Provider 同 document
 *   不串扰;生成的 app.gen.tsx 恒开)。无效 hash warn + 忽略、不回写。
 */

import { useCallback, useContext, useEffect, useMemo, useState, type ComponentType, type ReactNode } from "react";
import { mergePatches, NAV_TARGET, type Overrides, type Patch } from "./patches";
import { subscribePatches } from "./push";
import {
  applySchemeClass,
  persistScheme,
  readStoredScheme,
  systemPrefersDark,
  type ColorSchemeMode,
} from "./scheme";
import { ShadeRuntimeContext, type ShadeRuntimeStore } from "./store";

function parseHash(hash: string): string | null {
  return hash.startsWith("#/") && hash.length > 2 ? hash.slice(2) : null;
}

interface ShadeAppProviderProps {
  /** 初始页面名(= ShadeApp.pages[0];深链命中时被 hash 覆盖)。 */
  initial: string;
  /** 全页聚合的客户端所有 "anchor.prop"(anchor 以页面名为命名空间,聚合无冲突)。 */
  boundProps?: string[];
  /** 任一页面含 ServerRef 绑定即 true:App 层订阅 /_shade/push。 */
  push?: boolean;
  /** 全部页面名(深链 hash 校验);缺省空集 = 任何 hash 都不命中。 */
  pageNames?: string[];
  /** #/PageName 深链与 hash 同步;runtime 默认 false,生成的 App 恒传 true。 */
  deepLink?: boolean;
  /** 默认配色(= ShadeApp.color_scheme);localStorage 显式选择优先于此值。 */
  colorScheme?: ColorSchemeMode;
  children: ReactNode;
}

export function ShadeAppProvider({
  initial,
  boundProps,
  push,
  pageNames,
  deepLink,
  colorScheme,
  children,
}: ShadeAppProviderProps) {
  const linkEnabled = deepLink ?? false;
  const [names] = useState<Set<string>>(() => new Set(pageNames ?? []));
  const [currentPage, setCurrentPage] = useState<string>(() => {
    if (linkEnabled) {
      const target = parseHash(location.hash);
      if (target !== null && names.has(target)) {
        return target;
      }
    }
    return initial;
  });
  const [visitedPages, setVisitedPages] = useState<string[]>(() => [currentPage]);
  const [overrides, setOverrides] = useState<Overrides>({});
  const [bound] = useState<Set<string>>(() => new Set(boundProps ?? []));
  // 配色状态机:localStorage 显式选择 ?? app 默认 ?? system;class 由 resolvedDark 驱动
  const [scheme, setScheme] = useState<ColorSchemeMode>(() => readStoredScheme() ?? colorScheme ?? "system");
  const [systemDark, setSystemDark] = useState<boolean>(() => systemPrefersDark());
  const resolvedDark = scheme === "dark" || (scheme === "system" && systemDark);

  useEffect(() => {
    if (scheme !== "system" || typeof matchMedia !== "function") {
      return;
    }
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [scheme]);

  useEffect(() => {
    applySchemeClass(resolvedDark);
  }, [resolvedDark]);

  const setColorScheme = useCallback(
    (mode: ColorSchemeMode | "toggle") => {
      const next: ColorSchemeMode = mode === "toggle" ? (resolvedDark ? "light" : "dark") : mode;
      persistScheme(next);
      if (next === "system") {
        setSystemDark(systemPrefersDark()); // 回到跟随系统时立即重采样
      }
      setScheme(next);
    },
    [resolvedDark],
  );

  const navigateTo = useCallback(
    (page: string) => {
      setCurrentPage(page);
      setVisitedPages((prev) => (prev.includes(page) ? prev : [...prev, page]));
      if (linkEnabled && parseHash(location.hash) !== page) {
        location.hash = `#/${page}`; // 直赋产生历史条目,浏览器后退可用
      }
    },
    [linkEnabled],
  );

  useEffect(() => {
    if (!linkEnabled) {
      return;
    }
    // 启动规范化:不产生历史条目、不触发 hashchange
    if (parseHash(location.hash) !== currentPage) {
      history.replaceState(null, "", `#/${currentPage}`);
    }
    const onHashChange = () => {
      const target = parseHash(location.hash);
      if (target === null || !names.has(target)) {
        console.warn(`[pyshade] 未知页面 hash "${location.hash}",已忽略`);
        return; // 不回写规范 hash:双 Provider 共存与手改 URL 的宽容前提
      }
      navigateTo(target); // navigateTo 内 hash 已相等 → 不再回写,防环
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- currentPage 仅用于启动规范化,不随切页重挂监听
  }, [linkEnabled, names, navigateTo]);

  const applyPatches = useCallback(
    (patches: Patch[]) => {
      const rest = patches.filter((patch) => patch.target !== NAV_TARGET);
      if (rest.length > 0) {
        setOverrides((prev) => mergePatches(prev, rest, bound));
      }
      for (const patch of patches) {
        if (patch.target !== NAV_TARGET) continue;
        const page = patch.props.page;
        if (typeof page === "string") {
          navigateTo(page);
        } else {
          console.warn("[pyshade] $nav patch 缺少 page 字段,已忽略:", patch);
        }
      }
    },
    [bound, navigateTo],
  );

  const pushEnabled = push ?? false;
  useEffect(() => {
    if (!pushEnabled) {
      return;
    }
    // StrictMode 双挂载安全:cleanup 取消订阅,重连循环随之终止
    return subscribePatches(applyPatches);
  }, [pushEnabled, applyPatches]);

  const store = useMemo<ShadeRuntimeStore>(
    () => ({
      overrides,
      applyPatches,
      navigate: navigateTo,
      currentPage,
      visitedPages,
      colorScheme: scheme,
      resolvedDark,
      setColorScheme,
    }),
    [overrides, applyPatches, navigateTo, currentPage, visitedPages, scheme, resolvedDark, setColorScheme],
  );

  return <ShadeRuntimeContext.Provider value={store}>{children}</ShadeRuntimeContext.Provider>;
}

export function ShadeRouter({ pages, keepAlive }: { pages: Record<string, ComponentType>; keepAlive?: boolean }) {
  const store = useContext(ShadeRuntimeContext);
  if (store === null) {
    throw new Error("[pyshade] ShadeRouter 必须在 ShadeAppProvider 内使用");
  }
  if (!keepAlive) {
    const Page = pages[store.currentPage];
    if (Page === undefined) {
      // 编译期 check_app 已校验 navigate 目标;此处兜底服务端 $nav 传来未知页面名
      console.error(`[pyshade] 未知页面 "${store.currentPage}",可用页面:`, Object.keys(pages));
      return null;
    }
    return <Page />;
  }
  return (
    <>
      {store.visitedPages.map((name) => {
        const Page = pages[name];
        if (Page === undefined) {
          console.error(`[pyshade] 未知页面 "${name}",可用页面:`, Object.keys(pages));
          return null;
        }
        const active = name === store.currentPage;
        return (
          <div key={name} style={active ? undefined : { display: "none" }}>
            <Page />
          </div>
        );
      })}
    </>
  );
}
