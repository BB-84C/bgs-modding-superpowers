export async function runRules(rules, toolName, ctx, args) {
    const out = [];
    for (const rule of rules.filter((r) => r.appliesTo(toolName))) {
        try {
            const finding = await rule.evaluate(ctx, args, toolName);
            if (finding)
                out.push(finding);
        }
        catch (e) {
            out.push({
                code: `${rule.id}-error`,
                severity: "MEDIUM",
                decision: "warn",
                message: e instanceof Error ? e.message : String(e),
            });
        }
    }
    return out;
}
export function hasBlocking(findings) {
    return findings.some((finding) => finding.decision === "block");
}
