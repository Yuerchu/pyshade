import { shadeFetch } from "@/ipc/shadeFetch";
import type { PatchesEnvelope } from "./patches";

declare global {
  interface Window {
    __PYSHADE_IPC_COUNT__?: number;
  }
}

export async function invokeEvent(handlerId: string, payload: unknown): Promise<PatchesEnvelope> {
  if (typeof window !== "undefined") {
    window.__PYSHADE_IPC_COUNT__ = (window.__PYSHADE_IPC_COUNT__ ?? 0) + 1;
  }
  const res = await shadeFetch(`/_shade/event/${handlerId}`, {
    method: "POST",
    body: payload as object,
  });
  if (!res.ok) {
    throw new Error(`event ${handlerId} failed: ${res.status}`);
  }
  return (await res.json()) as PatchesEnvelope;
}
