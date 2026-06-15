const _registry = new Map();
export function registerTool(def) {
    _registry.set(def.name, def);
}
export function getTool(name) {
    return _registry.get(name);
}
export function getAllTools() {
    return [..._registry.values()];
}
/** Test-only reset. */
export function _clearToolsForTests() {
    _registry.clear();
}
