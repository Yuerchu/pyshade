import { useCallback, useState } from "react";
import { invokeEvent } from "./invoke";
import { isPatchesEnvelope, type Patch } from "./patches";

type Overrides = Record<string, Record<string, unknown>>;

interface PageRuntime {
  ov: <T>(anchor: string, prop: string, fallback: T) => T;
  fire: (handlerId: string, payload: unknown) => void;
}

export function usePageRuntime(): PageRuntime {
  const [overrides, setOverrides] = useState<Overrides>({});

  const ov = useCallback(
    <T>(anchor: string, prop: string, fallback: T): T => {
      const anchorOverrides = overrides[anchor];
      if (anchorOverrides !== undefined && prop in anchorOverrides) {
        return anchorOverrides[prop] as T;
      }
      return fallback;
    },
    [overrides],
  );

  const applyPatches = useCallback((patches: Patch[]) => {
    setOverrides((prev) => {
      const next = { ...prev };
      for (const patch of patches) {
        next[patch.target] = { ...next[patch.target], ...patch.props };
      }
      return next;
    });
  }, []);

  const fire = useCallback(
    (handlerId: string, payload: unknown) => {
      invokeEvent(handlerId, payload)
        .then((envelope) => {
          if (isPatchesEnvelope(envelope) && envelope.patches.length > 0) {
            applyPatches(envelope.patches);
          }
        })
        .catch((err: unknown) => {
          console.error(`[pyshade] event ${handlerId} failed:`, err);
        });
    },
    [applyPatches],
  );

  return { ov, fire };
}
