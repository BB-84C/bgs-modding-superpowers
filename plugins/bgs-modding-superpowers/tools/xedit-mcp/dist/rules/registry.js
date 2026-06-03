import { LOAD001 } from "./LOAD001.js";
export function createRegistry(rules) {
    const index = new Map();
    for (const r of rules) {
        for (const t of r.appliesTo) {
            const arr = index.get(t) ?? [];
            arr.push(r);
            index.set(t, arr);
        }
    }
    return {
        forTool: (tool) => index.get(tool) ?? [],
        all: () => [...rules],
    };
}
/** Default registry — wire all real seed rules here as they land. Batch 1: LOAD001 only. */
export function defaultRegistry() {
    return createRegistry([LOAD001]);
}
//# sourceMappingURL=registry.js.map