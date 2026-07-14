import { invokeEvent } from "./invoke";

declare global {
  interface Window {
    __pyshadeBench?: (n: number) => Promise<void>;
  }
}

async function bench(n: number): Promise<void> {
  const times: number[] = [];
  for (let i = 0; i < n; i++) {
    const start = performance.now();
    await invokeEvent("bench_echo", {});
    times.push(performance.now() - start);
  }
  times.sort((a, b) => a - b);
  const p50 = times[Math.floor(n * 0.5)] ?? 0;
  const p95 = times[Math.floor(n * 0.95)] ?? 0;
  const max = times[n - 1] ?? 0;
  console.table({ p50: p50.toFixed(2), p95: p95.toFixed(2), max: max.toFixed(2) });
}

if (typeof window !== "undefined") {
  window.__pyshadeBench = bench;
}
