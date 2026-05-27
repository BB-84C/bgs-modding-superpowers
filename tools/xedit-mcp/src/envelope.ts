import type {
  EnvelopeOk,
  EnvelopeRefusal,
  Rule,
  Finding,
  Warning,
  McpErrorCode,
} from "./types.js";

export function ok(
  input: Omit<EnvelopeOk, "ok" | "warnings"> & { warnings?: Warning[] },
): EnvelopeOk {
  return { ...input, ok: true, warnings: input.warnings ?? [] };
}

export function refuse(
  input: Omit<EnvelopeRefusal, "ok" | "warnings"> & { warnings?: Warning[] },
): EnvelopeRefusal {
  return { ...input, ok: false, warnings: input.warnings ?? [] };
}

export function fromRuleFinding(
  base: { tool: string },
  rule: Rule,
  finding: Finding,
): EnvelopeRefusal {
  return refuse({
    tool: base.tool,
    summary: `Refused by rule ${rule.id}: ${rule.description}`,
    code: `rule_${rule.id}` as McpErrorCode,
    severity: rule.riskLevel,
    hint: rule.suggestion,
    rationale: rule.rationale,
    matched: finding.matched,
    status: "refused",
  });
}
