import { useCallback, useState } from "react";
import { invokeEvent } from "./invoke";
import { isPatchesEnvelope, type Patch } from "./patches";

type Overrides = Record<string, Record<string, unknown>>;

interface PageRuntimeOptions {
  /** 客户端所有的 "anchor.prop"(表达式绑定):服务端 patch 到达时 warn + 丢弃(所有权公理的防御纵深)。 */
  boundProps?: string[];
}

interface PageRuntime {
  ov: <T>(anchor: string, prop: string, fallback: T) => T;
  fire: (handlerId: string, payload: unknown) => void;
}

export function usePageRuntime(options?: PageRuntimeOptions): PageRuntime {
  const [overrides, setOverrides] = useState<Overrides>({});
  // useState 惰性初始化:boundProps 由编译器生成,组件生命周期内不变
  const [boundProps] = useState<Set<string>>(() => new Set(options?.boundProps ?? []));

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

  const applyPatches = useCallback(
    (patches: Patch[]) => {
      setOverrides((prev) => {
        const next = { ...prev };
        for (const patch of patches) {
          const accepted: Record<string, unknown> = {};
          for (const [prop, value] of Object.entries(patch.props)) {
            if (boundProps.has(`${patch.target}.${prop}`)) {
              console.warn(
                `[pyshade] ${patch.target}.${prop} 已绑定客户端表达式,忽略服务端 patch(所有权在客户端)`,
              );
              continue;
            }
            accepted[prop] = value;
          }
          if (Object.keys(accepted).length > 0) {
            next[patch.target] = { ...next[patch.target], ...accepted };
          }
        }
        return next;
      });
    },
    [boundProps],
  );

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

  return { ov, fire };
}
