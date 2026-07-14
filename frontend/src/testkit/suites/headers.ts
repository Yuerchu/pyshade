/** case 1:x-pyshade-* headers 透传保真(path/query 阶梯 + 批量自定义 header)。 */

import { shadeFetch } from "@/ipc/shadeFetch";
import { check, makeCase, type CaseResult } from "../types";

const STEPS_KB = [1, 8, 16, 64];

export async function suiteHeaders(): Promise<CaseResult> {
  const result = makeCase("headers.fidelity");

  let maxOkKb = 0;
  for (const kb of STEPS_KB) {
    const seg = "p".repeat(kb * 1024);
    const queryValue = "v".repeat(kb * 1024);
    try {
      const res = await shadeFetch(`/_shade/_test/echo/${seg}?q=${queryValue}`, { method: "POST" });
      const data = (await res.json()) as { path: string; query: string };
      const ok = res.status === 200 && data.path.endsWith(seg) && data.query.length === queryValue.length + 2;
      if (!ok) {
        result.warnings.push(`${kb}KB 阶梯回显不完整(疑似截断)`);
        break;
      }
      maxOkKb = kb;
    } catch (err) {
      result.warnings.push(`${kb}KB 阶梯失败:${String(err)}`);
      break;
    }
  }
  result.metrics.max_ok_kb = maxOkKb;
  check(result, "path_query_8kb", maxOkKb >= 8, `max_ok=${maxOkKb}KB`);

  const custom: Record<string, string> = {};
  for (let i = 0; i < 64; i++) {
    custom[`x-t-${i}`] = `value-${i}`;
  }
  const res = await shadeFetch("/_shade/_test/echo/h", { method: "POST", headers: custom });
  const echoed = ((await res.json()) as { headers: Record<string, string> }).headers;
  const missing = Object.entries(custom).filter(([k, v]) => echoed[k] !== v);
  check(result, "custom_headers_64", missing.length === 0, missing.map(([k]) => k).join(","));

  return result;
}
