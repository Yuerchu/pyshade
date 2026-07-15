/**
 * 编译产物级 SPA 验证(M2 Phase 7):驱动真实 task_board 应用的 DOM。
 * - spa.each_click:点击 Each 第 N 项的模板按钮 → item_key 定位 → 整表替换 patch 回来重渲染;
 * - spa.navigate:客户端 rt.navigate 双向切页 + 服务端 Navigate($nav patch)。
 * 加载的 dist 不是 task_board 时自动 skip(login_form harness 跑全量 suite 不受影响)。
 */

import { check, makeCase, type CaseResult } from "../types";

const POLL_MS = 100;

function buttonsByText(text: string): HTMLButtonElement[] {
  return Array.from(document.querySelectorAll("button")).filter((b) => b.textContent?.trim() === text);
}

function textsOf(selector: string): string[] {
  return Array.from(document.querySelectorAll(selector)).map((el) => el.textContent?.trim() ?? "");
}

function summaryText(): string | null {
  return textsOf("p").find((t) => t.startsWith("共 ")) ?? null;
}

function doneLabelCount(): number {
  return textsOf("p").filter((t) => t === "已完成").length;
}

async function waitFor(pred: () => boolean, timeoutMs = 8000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (pred()) return true;
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }
  return pred();
}

function isTaskBoard(): boolean {
  return buttonsByText("切换状态").length > 0 || buttonsByText("查看统计").length > 0;
}

export async function suiteSpaEachClick(): Promise<CaseResult> {
  const result = makeCase("spa.each_click");
  if (!(await waitFor(isTaskBoard, 3000))) {
    result.status = "skip";
    result.detail.reason = "当前 dist 不是 task_board";
    return result;
  }

  check(result, "initial_three_items", buttonsByText("切换状态").length === 3);
  check(result, "initial_one_done", doneLabelCount() === 1, `done=${doneLabelCount()}`);

  // 点第 2 项(id=2,初始 done=True)→ item_key 定位 → done 翻转为 false
  buttonsByText("切换状态")[1]?.click();
  const cleared = await waitFor(() => doneLabelCount() === 0);
  check(result, "second_item_toggled_by_key", cleared, `done=${doneLabelCount()}`);
  const summaryUpdated = await waitFor(() => summaryText() === "共 3 项,已完成 0 项");
  check(result, "summary_patched", summaryUpdated, summaryText() ?? "(无摘要)");
  return result;
}

export async function suiteSpaNavigate(): Promise<CaseResult> {
  const result = makeCase("spa.navigate");
  if (!(await waitFor(isTaskBoard, 3000))) {
    result.status = "skip";
    result.detail.reason = "当前 dist 不是 task_board";
    return result;
  }

  // 客户端导航:看板 → 统计
  buttonsByText("查看统计")[0]?.click();
  const statsMounted = await waitFor(() => buttonsByText("返回看板").length === 1);
  check(result, "stats_mounted", statsMounted);
  check(result, "board_unmounted", buttonsByText("切换状态").length === 0);

  // 客户端导航:统计 → 看板(字符串目标);ServerState 存活
  buttonsByText("返回看板")[0]?.click();
  const boardBack = await waitFor(() => buttonsByText("切换状态").length === 3);
  check(result, "board_state_survives", boardBack, `items=${buttonsByText("切换状态").length}`);

  // 服务端 Navigate:先把第 1 项标记完成,再从统计页"清理已完成并返回"
  buttonsByText("切换状态")[0]?.click();
  await waitFor(() => doneLabelCount() === 1);
  buttonsByText("查看统计")[0]?.click();
  await waitFor(() => buttonsByText("清理已完成并返回").length === 1);
  buttonsByText("清理已完成并返回")[0]?.click();
  const boardCleaned = await waitFor(() => buttonsByText("切换状态").length === 2);
  check(result, "server_navigate_with_data_patch", boardCleaned, `items=${buttonsByText("切换状态").length}`);
  const summaryOk = await waitFor(() => summaryText() === "共 2 项,已完成 0 项");
  check(result, "summary_after_clear", summaryOk, summaryText() ?? "(无摘要)");
  return result;
}
