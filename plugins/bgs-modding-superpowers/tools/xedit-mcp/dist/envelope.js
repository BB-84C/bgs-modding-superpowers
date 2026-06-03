export function ok(input) {
    return { ...input, ok: true, warnings: input.warnings ?? [] };
}
export function refuse(input) {
    return { ...input, ok: false, warnings: input.warnings ?? [] };
}
export function fromRuleFinding(base, rule, finding) {
    return refuse({
        tool: base.tool,
        summary: `Refused by rule ${rule.id}: ${rule.description}`,
        code: `rule_${rule.id}`,
        severity: rule.riskLevel,
        hint: rule.suggestion,
        rationale: rule.rationale,
        matched: finding.matched,
        status: "refused",
    });
}
//# sourceMappingURL=envelope.js.map