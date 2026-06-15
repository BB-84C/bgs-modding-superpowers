/**
 * Rule evaluation — runs all applicable rules against a tool call.
 *
 * Each rule returns RuleFinding | null. Findings with decision="block"
 * cause the call to be refused before the handler runs.
 */
import type { Rule, RuleFinding, ToolContext } from "../types.js";
export declare function runRules(rules: Rule[], toolName: string, ctx: ToolContext, args: Record<string, unknown>): Promise<RuleFinding[]>;
export declare function hasBlocking(findings: RuleFinding[]): boolean;
