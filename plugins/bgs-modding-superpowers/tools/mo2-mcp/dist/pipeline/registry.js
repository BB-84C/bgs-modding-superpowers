const rules = [];
export function registerRule(rule) {
    rules.push(rule);
}
export function getAllRules() {
    return [...rules];
}
/** Reset for tests only. */
export function _clearRulesForTests() {
    rules.length = 0;
}
