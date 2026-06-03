import { fromRuleFinding } from "../envelope.js";
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
export async function runRules(input) {
    const blockHigh = input.blockHigh ?? true;
    const rules = input.registry.forTool(input.tool);
    const warnings = [];
    const ruleHits = [];
    for (const rule of rules) {
        const finding = rule.check({ tool: input.tool, args: input.args, ctx: input.ctx });
        if (!finding)
            continue;
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
//# sourceMappingURL=rules.js.map