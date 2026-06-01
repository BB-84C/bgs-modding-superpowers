import { fromRuleFinding } from "../envelope.js";
export async function runRules(input) {
    const blockHigh = input.blockHigh ?? true;
    const rules = input.registry.forTool(input.tool);
    for (const rule of rules) {
        const finding = rule.check({ tool: input.tool, args: input.args, ctx: input.ctx });
        if (!finding)
            continue;
        if (rule.riskLevel === "CRITICAL" || (rule.riskLevel === "HIGH" && blockHigh)) {
            return fromRuleFinding({ tool: input.tool }, rule, finding);
        }
        // MEDIUM (and HIGH when blockHigh=false) fall through; collected as warnings by callers.
    }
    return null;
}
//# sourceMappingURL=rules.js.map