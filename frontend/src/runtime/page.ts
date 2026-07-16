import { useCallback, useContext, useEffect, useState } from "react";
import { invokeEvent } from "./invoke";
import { isPatchesEnvelope, mergePatches, NAV_TARGET, type Overrides, type Patch } from "./patches";
import { subscribePatches } from "./push";
import { applySchemeClass, persistScheme, resolveDark, type ColorSchemeMode } from "./scheme";
import { ShadeRuntimeContext } from "./store";

interface PageRuntimeOptions {
  /** 客户端所有的 "anchor.prop"(表达式绑定):服务端 patch 到达时 warn + 丢弃(所有权公理的防御纵深)。 */
  boundProps?: string[];
  /** 页面含 ServerRef 绑定时由编译器置 true:订阅 /_shade/push,后台变更自动到达。 */
  push?: boolean;
}

interface PageRuntime {
  ov: <T>(anchor: string, prop: string, fallback: T) => T;
  fire: (handlerId: string, payload: unknown) => void;
  navigate: (page: string) => void;
  setColorScheme: (mode: ColorSchemeMode | "toggle") => void;
}

/**
 * 页面运行时,双模式(M2 Phase 5):
 * - 有 ShadeAppProvider(生产 App):overrides/patch 过滤/push 订阅都在 App 级共享 store,
 *   页面级 boundProps/push 选项为无害 no-op(App 已聚合);
 * - 无 Provider(单页挂载/单测):回落页面本地 store,行为与 M1 一致。
 */
export function usePageRuntime(options?: PageRuntimeOptions): PageRuntime {
  const app = useContext(ShadeRuntimeContext);
  // 本地模式的兜底 store;有 Provider 时不使用(hooks 须无条件调用)
  const [localOverrides, setLocalOverrides] = useState<Overrides>({});
  // useState 惰性初始化:boundProps 由编译器生成,组件生命周期内不变
  const [boundProps] = useState<Set<string>>(() => new Set(options?.boundProps ?? []));

  const localApply = useCallback(
    (patches: Patch[]) => {
      const rest = patches.filter((patch) => patch.target !== NAV_TARGET);
      if (rest.length < patches.length) {
        console.warn("[pyshade] 无 ShadeAppProvider,$nav patch 已忽略");
      }
      if (rest.length > 0) {
        setLocalOverrides((prev) => mergePatches(prev, rest, boundProps));
      }
    },
    [boundProps],
  );

  const applyPatches = app !== null ? app.applyPatches : localApply;
  const overrides = app !== null ? app.overrides : localOverrides;

  const ov = useCallback(
    <T>(anchor: string, prop: string, fallback: T): T => {
      const anchorOverrides = overrides[anchor];
      if (anchorOverrides !== undefined && prop in anchorOverrides) {
        return anchorOverrides[prop] as T;
      }
      return fallback;
    },
    [overrides],
  );

  const pushEnabled = (options?.push ?? false) && app === null;
  useEffect(() => {
    if (!pushEnabled) {
      return;
    }
    // StrictMode 双挂载安全:cleanup 取消订阅,重连循环随之终止。
    // 回落路径不渲染 Connection Lost 徽标(单页挂载/单测形态;fixed 定位会逃逸容器,
    // testkit 双 Provider 同 document 会串扰)——生成的 App 恒有 Provider,徽标归 App 层。
    return subscribePatches(applyPatches);
  }, [pushEnabled, applyPatches]);

  const fire = useCallback(
    (handlerId: string, payload: unknown) => {
      invokeEvent(handlerId, payload)
        .then((envelope) => {
          if (isPatchesEnvelope(envelope) && envelope.patches.length > 0) {
            applyPatches(envelope.patches);
          }
        })
        .catch((err: unknown) => {
          console.error(`[pyshade] event ${handlerId} failed:`, err);
        });
    },
    [applyPatches],
  );

  const warnNavigate = useCallback((page: string) => {
    console.warn(`[pyshade] 无 ShadeAppProvider,navigate("${page}") 无效`);
  }, []);
  const navigate = app !== null ? app.navigate : warnNavigate;

  // 无 Provider 回落:直接操作 documentElement class + localStorage(单页挂载/单测可用)
  const fallbackSetColorScheme = useCallback((mode: ColorSchemeMode | "toggle") => {
    const currentDark = document.documentElement.classList.contains("dark");
    const next: ColorSchemeMode = mode === "toggle" ? (currentDark ? "light" : "dark") : mode;
    persistScheme(next);
    applySchemeClass(resolveDark(next));
  }, []);
  const setColorScheme = app !== null ? app.setColorScheme : fallbackSetColorScheme;

  return { ov, fire, navigate, setColorScheme };
}
