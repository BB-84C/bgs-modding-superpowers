export function ok(input) {
    return { ...input, ok: true, warnings: input.warnings ?? [] };
}
export function refuse(input) {
    return { ...input, ok: false, warnings: input.warnings ?? [] };
}
export { KB_ERROR_CODES } from "./types.js";
//# sourceMappingURL=index.js.map