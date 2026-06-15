/**
 * Rule registry — side-effect imports register their rules here.
 *
 * Rules are added to a module-level array via registerRule(). Pipeline
 * runner reads getAllRules() to iterate them in registration order.
 */
import type { Rule } from "../types.js";
export declare function registerRule(rule: Rule): void;
export declare function getAllRules(): Rule[];
/** Reset for tests only. */
export declare function _clearRulesForTests(): void;
