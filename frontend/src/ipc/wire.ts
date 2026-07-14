/**
 * wire 协议解码:src/pyshade/asgi/_wire.py 的前端镜像。
 * 协议由 Python 侧 golden bytes 测试锁定;本文件的常量与帧格式不得单方面变更。
 */

export const ASGI_COMMAND = "__pyshade_asgi__";
export const ENVELOPE_MAGIC = [0x50, 0x53, 0x41, 0x31]; // "PSA1"

export const FRAME_BODY = 0x02;
export const FRAME_END = 0x03;
export const FRAME_ERROR = 0x04;

export interface ResponseHead {
  status: number;
  headers: [string, string][];
  stream: boolean;
}

export class WireError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

/** PSA1 单帧响应封包解码:magic + u32 meta_len(大端) + meta JSON + body。 */
export function decodeEnvelope(frame: Uint8Array): { head: ResponseHead; body: Uint8Array } {
  if (frame.length < 8 || !ENVELOPE_MAGIC.every((b, i) => frame[i] === b)) {
    throw new WireError("bad_envelope", "invalid envelope magic");
  }
  const view = new DataView(frame.buffer, frame.byteOffset, frame.byteLength);
  const metaLen = view.getUint32(4, false);
  if (frame.length < 8 + metaLen) {
    throw new WireError("bad_envelope", "envelope meta truncated");
  }
  let meta: { status: number; headers: [string, string][]; stream?: boolean };
  try {
    meta = JSON.parse(new TextDecoder().decode(frame.subarray(8, 8 + metaLen))) as typeof meta;
  } catch {
    throw new WireError("bad_envelope", "envelope meta is not valid JSON");
  }
  return {
    head: { status: meta.status, headers: meta.headers, stream: meta.stream ?? false },
    body: frame.subarray(8 + metaLen),
  };
}

export type Frame =
  | { kind: "body"; chunk: Uint8Array }
  | { kind: "end" }
  | { kind: "error"; code: string; message: string };

/** Channel 流式帧解码:tag 字节前缀。 */
export function decodeFrame(data: Uint8Array): Frame {
  if (data.length === 0) {
    throw new WireError("bad_frame", "empty frame");
  }
  const tag = data[0];
  if (tag === FRAME_BODY) {
    return { kind: "body", chunk: data.subarray(1) };
  }
  if (tag === FRAME_END) {
    return { kind: "end" };
  }
  if (tag === FRAME_ERROR) {
    const payload = JSON.parse(new TextDecoder().decode(data.subarray(1))) as {
      code: string;
      message: string;
    };
    return { kind: "error", code: payload.code, message: payload.message };
  }
  throw new WireError("bad_frame", `unknown frame tag: ${tag}`);
}

/** reject 载荷(传输层错误)解析。 */
export function parseReject(raw: unknown): WireError {
  if (typeof raw === "string") {
    try {
      const payload = JSON.parse(raw) as { code?: string; message?: string };
      return new WireError(payload.code ?? "unknown", payload.message ?? raw);
    } catch {
      return new WireError("unknown", raw);
    }
  }
  return new WireError("unknown", String(raw));
}
