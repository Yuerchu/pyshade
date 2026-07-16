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

  // URL 解析统一(发版前审查):IPC 与 HTTP 模式对同一 path 的解析结果必须一致
  // ①query 自身含 ?(合法):split("?", 2) 的 limit 语义会静默截断尾段
  const doubleQ = await shadeFetch("/_shade/_test/echo/a?x=1?y=2", { method: "POST" });
  const doubleQData = (await doubleQ.json()) as { query: string };
  check(result, "query_with_question_mark", doubleQData.query === "x=1?y=2", `got=${doubleQData.query}`);

  // ②非 ASCII query:IPC 模式此前原样进 invoke header(Headers 校验会炸);URL 规范化后 percent-encode
  const unicode = await shadeFetch("/_shade/_test/echo/a?q=中文", { method: "POST" });
  const unicodeData = (await unicode.json()) as { query: string };
  check(result, "non_ascii_query", decodeURIComponent(unicodeData.query) === "q=中文", `got=${unicodeData.query}`);

  // ③已编码段不双重编码:encodeURI(%20) 会变 %2520,服务端解出 "%20" 而非空格
  const preEncoded = await shadeFetch("/_shade/_test/echo/a%20b", { method: "POST" });
  const preEncodedData = (await preEncoded.json()) as { path: string };
  check(result, "no_double_percent_encoding", preEncodedData.path.endsWith("/a b"), `got=${preEncodedData.path}`);

  return result;
}
