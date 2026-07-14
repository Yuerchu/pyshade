/** case 4:空 body 约定(Uint8Array(0) → InvokeBody::Raw;undefined 对照组行为记录)。 */

import { invoke } from "@tauri-apps/api/core";
import { shadeFetch } from "@/ipc/shadeFetch";
import { ASGI_COMMAND } from "@/ipc/wire";
import { check, makeCase, type CaseResult } from "../types";

export async function suiteEmptyBody(): Promise<CaseResult> {
  const result = makeCase("body.empty_raw");

  const res = await shadeFetch("/_shade/_test/sink", { method: "POST" });
  const data = (await res.json()) as { len: number };
  check(result, "empty_uint8array_is_raw", res.status === 200 && data.len === 0, `len=${data.len}`);

  // 对照组:undefined body 走 InvokeBody::Json,预期被 pytauri bind_to 拒绝(事实记录,不判 pass/fail)
  if ("__TAURI_INTERNALS__" in window) {
    let rejected = false;
    try {
      await invoke("plugin:pytauri|pyfunc", undefined, {
        headers: {
          pyfunc: ASGI_COMMAND,
          "x-pyshade-method": "POST",
          "x-pyshade-path": "/_shade/_test/sink",
        },
      });
    } catch {
      rejected = true;
    }
    result.detail.undefined_body_rejected = rejected;
  }

  return result;
}
