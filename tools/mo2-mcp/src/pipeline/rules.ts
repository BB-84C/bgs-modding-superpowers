/**
 * Rule evaluation — runs all applicable rules against a tool call.
 *
 * Each rule returns RuleFinding | null. Findings with decision="block"
 * cause the call to be refused before the handler runs.
 */
import type { Rule, RuleFinding, ToolContext } from "../types.js";

export async function runRules(
  rules: Rule[],
  toolName: string,
  ctx: ToolContext,
  args: Record<string, unknown>,
): Promise<RuleFinding[]> {
  const out: RuleFinding[] = [];
  for (const rule of rules.filter((r) => r.appliesTo(toolName))) {
    try {
      const finding = await rule.evaluate(ctx, args);
      if (finding) out.push(finding);
    } catch (e) {
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

export function hasBlocking(findings: RuleFinding[]): boolean {
  return findings.some((finding) => finding.decision === "block");
}
