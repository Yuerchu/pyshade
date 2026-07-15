export interface Patch {
  target: string;
  props: Record<string, unknown>;
}

export interface PatchesEnvelope {
  patches: Patch[];
}

export function isPatchesEnvelope(data: unknown): data is PatchesEnvelope {
  if (typeof data !== "object" || data === null) return false;
  const obj = data as Record<string, unknown>;
  return Array.isArray(obj.patches);
}

/** 服务端 patch 的保留地址(M2 Phase 5):导航指令,不进 overrides,由 App 级 store 消费。 */
export const NAV_TARGET = "$nav";

export type Overrides = Record<string, Record<string, unknown>>;

/**
 * 合并 patches 进 overrides(纯函数,App 级与页面级 store 共用)。
 * boundProps 中的 "anchor.prop" 归客户端所有:warn + 丢弃(所有权公理的防御纵深)。
 */
export function mergePatches(prev: Overrides, patches: Patch[], boundProps: ReadonlySet<string>): Overrides {
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
}
