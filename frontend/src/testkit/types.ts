/** 与 src/pyshade/testing/_report.py 的 pydantic 模型对应。 */

export interface Assertion {
  name: string;
  ok: boolean;
  detail?: string;
}

export interface CaseResult {
  id: string;
  status: "pass" | "fail" | "error" | "skip";
  source: "js" | "python";
  assertions: Assertion[];
  metrics: Record<string, number>;
  warnings: string[];
  detail: Record<string, unknown>;
}

export interface RunConfig {
  suites?: string[];
  [key: string]: unknown;
}

export type SuiteFn = (config: RunConfig) => Promise<CaseResult>;

export function makeCase(id: string): CaseResult {
  return { id, status: "pass", source: "js", assertions: [], metrics: {}, warnings: [], detail: {} };
}

export function check(result: CaseResult, name: string, ok: boolean, detail = ""): void {
  result.assertions.push({ name, ok, detail });
  if (!ok && result.status === "pass") {
    result.status = "fail";
  }
}

export function percentile(values: number[], q: number): number {
  if (values.length === 0) return 0;
  const ordered = [...values].sort((a, b) => a - b);
  const index = Math.min(ordered.length - 1, Math.max(0, Math.round((q / 100) * ordered.length) - 1));
  return ordered[index];
}
