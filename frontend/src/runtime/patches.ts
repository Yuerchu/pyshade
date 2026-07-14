export interface Patch {
  target: string;
  props: Record<string, unknown>;
}

export interface PatchesEnvelope {
  patches: Patch[];
}

export function isPatchesEnvelope(data: unknown): data is PatchesEnvelope {
  if (typeof data !== "object" || data === null) return false;
  const obj = data as Record<string, unknown>;
  return Array.isArray(obj.patches);
}
