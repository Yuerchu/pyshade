/** case 2:Channel 帧与 invoke resolve 的次序竞态(50 并发快速流,校验完整性)。 */

import { shadeFetch } from "@/ipc/shadeFetch";
import { check, makeCase, type CaseResult } from "../types";

const FRAME_LEN = 7 + 64; // '%06d:' + 64 字节填充(_routes.py stream_fast 格式)
const FRAMES = 20;
const CONCURRENCY = 50;

async function oneStream(): Promise<boolean> {
  const res = await shadeFetch(`/_shade/_test/stream_fast?frames=${FRAMES}`);
  const buf = new Uint8Array(await res.arrayBuffer());
  if (buf.length !== FRAMES * FRAME_LEN) {
    return false;
  }
  const decoder = new TextDecoder();
  for (let i = 0; i < FRAMES; i++) {
    const head = decoder.decode(buf.subarray(i * FRAME_LEN, i * FRAME_LEN + 7));
    if (head !== `${String(i).padStart(6, "0")}:`) {
      return false;
    }
  }
  return true;
}

export async function suiteStreaming(): Promise<CaseResult> {
  const result = makeCase("streaming.race");
  const outcomes = await Promise.all(
    Array.from({ length: CONCURRENCY }, () => oneStream().catch(() => false)),
  );
  const okCount = outcomes.filter(Boolean).length;
  result.metrics.streams_ok = okCount;
  result.metrics.streams_total = CONCURRENCY;
  check(result, "all_streams_intact", okCount === CONCURRENCY, `${okCount}/${CONCURRENCY}`);
  return result;
}
