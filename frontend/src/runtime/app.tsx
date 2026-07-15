/**
 * App 级运行时骨架(M2 Phase 5):app.gen.tsx 只聚合参数与页面表,骨架在此手写。
 *
 * - overrides 提升 App 级共享:服务端 Update 不因切页蒸发;
 * - push 订阅提升 App 层:切页不断连、他页停留时后台推送不丢;
 * - $nav 保留地址:服务端 Navigate 编码为 patch,在此拦截切页;
 * - 页面状态 unmount 即丢(定案):跨页存活的归宿是 ServerState。
 */

import { useCallback, useContext, useEffect, useMemo, useState, type ComponentType, type ReactNode } from "react";
import { mergePatches, NAV_TARGET, type Overrides, type Patch } from "./patches";
import { subscribePatches } from "./push";
import { ShadeRuntimeContext, type ShadeRuntimeStore } from "./store";

interface ShadeAppProviderProps {
  /** 初始页面名(= ShadeApp.pages[0];深链归 M3)。 */
  initial: string;
  /** 全页聚合的客户端所有 "anchor.prop"(anchor 以页面名为命名空间,聚合无冲突)。 */
  boundProps?: string[];
  /** 任一页面含 ServerRef 绑定即 true:App 层订阅 /_shade/push。 */
  push?: boolean;
  children: ReactNode;
}

export function ShadeAppProvider({ initial, boundProps, push, children }: ShadeAppProviderProps) {
  const [currentPage, setCurrentPage] = useState<string>(initial);
  const [overrides, setOverrides] = useState<Overrides>({});
  const [bound] = useState<Set<string>>(() => new Set(boundProps ?? []));

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
          setCurrentPage(page);
        } else {
          console.warn("[pyshade] $nav patch 缺少 page 字段,已忽略:", patch);
        }
      }
    },
    [bound],
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
    () => ({ overrides, applyPatches, navigate: setCurrentPage, currentPage }),
    [overrides, applyPatches, currentPage],
  );

  return <ShadeRuntimeContext.Provider value={store}>{children}</ShadeRuntimeContext.Provider>;
}

export function ShadeRouter({ pages }: { pages: Record<string, ComponentType> }) {
  const store = useContext(ShadeRuntimeContext);
  if (store === null) {
    throw new Error("[pyshade] ShadeRouter 必须在 ShadeAppProvider 内使用");
  }
  const Page = pages[store.currentPage];
  if (Page === undefined) {
    // 编译期 check_app 已校验 navigate 目标;此处兜底服务端 $nav 传来未知页面名
    console.error(`[pyshade] 未知页面 "${store.currentPage}",可用页面:`, Object.keys(pages));
    return null;
  }
  return <Page />;
}
