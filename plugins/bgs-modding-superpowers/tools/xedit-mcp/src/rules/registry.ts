import type { Rule } from "../types.js";
import { LOAD001 } from "./LOAD001.js";

export interface Registry {
  forTool(tool: string): Rule[];
  all(): Rule[];
}

export function createRegistry(rules: Rule[]): Registry {
  const index = new Map<string, Rule[]>();
  for (const r of rules) {
    for (const t of r.appliesTo) {
      const arr = index.get(t) ?? [];
      arr.push(r);
      index.set(t, arr);
    }
  }
  return {
    forTool: (tool) => index.get(tool) ?? [],
    all: () => [...rules],
  };
}

/** Default registry — wire all real seed rules here as they land. Batch 1: LOAD001 only. */
export function defaultRegistry(): Registry {
  return createRegistry([LOAD001]);
}
