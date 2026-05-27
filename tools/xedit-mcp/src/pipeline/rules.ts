import type { EnvelopeRefusal, ToolContext } from "../types.js";
import { fromRuleFinding } from "../envelope.js";
import type { Registry } from "../rules/registry.js";

export interface RunRulesInput {
  tool: string;
  args: Record<string, unknown>;
  ctx: ToolContext;
  registry: Registry;
  /** Block HIGH (default true); CRITICAL always blocks; MEDIUM always warns only. */
  blockHigh?: boolean;
}

export async function runRules(input: RunRulesInput): Promise<EnvelopeRefusal | null> {
  const blockHigh = input.blockHigh ?? true;
  const rules = input.registry.forTool(input.tool);
  for (const rule of rules) {
    const finding = rule.check({ tool: input.tool, args: input.args, ctx: input.ctx });
    if (!finding) continue;
    if (rule.riskLevel === "CRITICAL" || (rule.riskLevel === "HIGH" && blockHigh)) {
      return fromRuleFinding({ tool: input.tool }, rule, finding);
    }
    // MEDIUM (and HIGH when blockHigh=false) fall through; collected as warnings by callers.
  }
  return null;
}
