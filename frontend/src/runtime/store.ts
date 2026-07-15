/**
 * App 级共享 store 的 context 定义(M2 Phase 5)。
 * 独立文件:app.tsx(Provider/Router)与 page.ts(usePageRuntime 双模式)都消费,避免环形依赖。
 */

import { createContext } from "react";
import type { Overrides, Patch } from "./patches";

export interface ShadeRuntimeStore {
  /** 全页共享的 overrides:服务端 Update 不因切页蒸发(跨页存活的定案语义)。 */
  overrides: Overrides;
  /** boundProps 过滤 + $nav 拦截后合并;push 订阅与 fire 回包共用。 */
  applyPatches: (patches: Patch[]) => void;
  navigate: (page: string) => void;
  currentPage: string;
  /** 访问过的页面(去重,访问序);Router keepAlive 据此保持挂载。 */
  visitedPages: string[];
}

/** 无 Provider(单页挂载/单测)时为 null,usePageRuntime 回落页面本地 store。 */
export const ShadeRuntimeContext = createContext<ShadeRuntimeStore | null>(null);
