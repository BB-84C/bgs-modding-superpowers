/**
 * Rule registry — side-effect imports register their rules here.
 *
 * Rules are added to a module-level array via registerRule(). Pipeline
 * runner reads getAllRules() to iterate them in registration order.
 */
import type { Rule } from "../types.js";

const rules: Rule[] = [];

export function registerRule(rule: Rule): void {
  rules.push(rule);
}

export function getAllRules(): Rule[] {
  return [...rules];
}

/** Reset for tests only. */
export function _clearRulesForTests(): void {
  rules.length = 0;
}
