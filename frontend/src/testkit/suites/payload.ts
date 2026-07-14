/** case 3:大 body 双向传输(尺寸阶梯 + 完整性 + 吞吐)。 */

import { shadeFetch } from "@/ipc/shadeFetch";
import { check, makeCase, type CaseResult } from "../types";

const STEPS_MB = [1, 8, 32];
const MB = 1024 * 1024;

function patternBuffer(size: number): Uint8Array {
  const buf = new Uint8Array(size);
  for (let i = 0; i < size; i++) {
    buf[i] = i % 256;
  }
  return buf;
}

async function sha256hex(buf: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", buf as unknown as ArrayBuffer);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function suitePayload(): Promise<CaseResult> {
  const result = makeCase("payload.size");

  let downOk = 0;
  for (const mb of STEPS_MB) {
    try {
      const t0 = performance.now();
      const res = await shadeFetch(`/_shade/_test/blob?size=${mb * MB}`);
      const buf = new Uint8Array(await res.arrayBuffer());
      const elapsed = performance.now() - t0;
      const spotOk =
        buf.length === mb * MB &&
        buf[0] === 0 &&
        buf[255] === 255 &&
        buf[buf.length - 1] === (buf.length - 1) % 256;
      if (!spotOk) {
        result.warnings.push(`下行 ${mb}MB 内容校验失败`);
        break;
      }
      downOk = mb;
      result.metrics[`down_${mb}mb_ms`] = Math.round(elapsed);
    } catch (err) {
      result.warnings.push(`下行 ${mb}MB 失败:${String(err)}`);
      break;
    }
  }

  let upOk = 0;
  for (const mb of STEPS_MB) {
    try {
      const buf = patternBuffer(mb * MB);
      const expected = await sha256hex(buf);
      const t0 = performance.now();
      const res = await shadeFetch("/_shade/_test/sink", { method: "POST", body: buf });
      const elapsed = performance.now() - t0;
      const data = (await res.json()) as { len: number; sha256: string };
      if (data.len !== mb * MB || data.sha256 !== expected) {
        result.warnings.push(`上行 ${mb}MB 完整性校验失败`);
        break;
      }
      upOk = mb;
      result.metrics[`up_${mb}mb_ms`] = Math.round(elapsed);
    } catch (err) {
      result.warnings.push(`上行 ${mb}MB 失败:${String(err)}`);
      break;
    }
  }

  result.metrics.max_ok_mb = Math.min(downOk, upOk);
  check(result, "bidirectional_8mb", downOk >= 8 && upOk >= 8, `down=${downOk}MB up=${upOk}MB`);
  return result;
}
