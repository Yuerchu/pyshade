import type { PatchesEnvelope } from "./patches";

declare global {
  interface Window {
    __PYSHADE_IPC_COUNT__?: number;
  }
}

async function invokeViaFetch(handlerId: string, payload: unknown): Promise<PatchesEnvelope> {
  const res = await fetch(`/_shade/event/${handlerId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`event ${handlerId} failed: ${res.status}`);
  }
  return (await res.json()) as PatchesEnvelope;
}

export async function invokeEvent(handlerId: string, payload: unknown): Promise<PatchesEnvelope> {
  if (typeof window !== "undefined") {
    window.__PYSHADE_IPC_COUNT__ = (window.__PYSHADE_IPC_COUNT__ ?? 0) + 1;
  }
  return invokeViaFetch(handlerId, payload);
}
