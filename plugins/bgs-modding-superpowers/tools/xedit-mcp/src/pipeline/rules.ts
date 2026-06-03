import type { EnvelopeRefusal, ToolContext, Warning } from "../types.js";
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

export interface RunRulesOutput {
  /** Non-null if a blocking rule tripped (CRITICAL always; HIGH when blockHigh=true). */
  refusal: EnvelopeRefusal | null;
  /** Warnings collected from non-blocking rule hits (MEDIUM always; HIGH when blockHigh=false). */
  warnings: Warning[];
  /** Rule IDs that triggered (blocking OR warning) — useful for audit ruleHits. */
  ruleHits: string[];
}

/**
 * Run all rules registered for `tool`.
 *
 * Batch 2 (carry-forward #4): MEDIUM findings used to be silently discarded.
 * They now surface in `warnings`, which callers attach to the success
 * envelope's `warnings` array (see `EnvelopeOk.warnings` in `types.ts`).
 *
 * Blocking semantics:
 *   - CRITICAL — always blocks (first match wins, returned as `refusal`).
 *   - HIGH     — blocks when `blockHigh` is true (default); otherwise warns.
 *   - MEDIUM   — never blocks; always warns.
 *
 * On the first blocking finding the run short-circuits: only warnings
 * collected from rules that ran before the blocker are returned alongside the
 * refusal, so callers can still surface them on the refusal envelope if they
 * choose.
 */
export async function runRules(input: RunRulesInput): Promise<RunRulesOutput> {
  const blockHigh = input.blockHigh ?? true;
  const rules = input.registry.forTool(input.tool);
  const warnings: Warning[] = [];
  const ruleHits: string[] = [];
  for (const rule of rules) {
    const finding = rule.check({ tool: input.tool, args: input.args, ctx: input.ctx });
    if (!finding) continue;
    ruleHits.push(rule.id);
    if (rule.riskLevel === "CRITICAL" || (rule.riskLevel === "HIGH" && blockHigh)) {
      return {
        refusal: fromRuleFinding({ tool: input.tool }, rule, finding),
        warnings,
        ruleHits,
      };
    }
    // MEDIUM (always) and HIGH (when blockHigh=false) -> warn, do not block.
    warnings.push({
      code: `rule_${rule.id}`,
      message: `${rule.description}: ${finding.message}`,
      severity: rule.riskLevel === "MEDIUM" ? "MEDIUM" : "HIGH",
    });
  }
  return { refusal: null, warnings, ruleHits };
}
