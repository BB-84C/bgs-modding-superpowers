import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
export function resolvePluginRoot(moduleUrl) {
    return resolve(dirname(fileURLToPath(moduleUrl)), "..", "..", "..", "..");
}
export function defaultCacheRoot() {
    // Unified with xtl/bgs-translator and other agent-side tooling: the cache
    // root is ~/.bgs-modding-superpowers/kb/packs on every platform. The legacy
    // paths (%LOCALAPPDATA%\bgs-modding-superpowers\kb on Windows; $XDG_CACHE_HOME
    // or ~/.cache on Linux/macOS) are no longer used. Users with a legacy install
    // can move ~/.cache/bgs-modding-superpowers/kb or
    // %LOCALAPPDATA%/bgs-modding-superpowers/kb to the new location, or expose
    // the old roots via $env:BGS_KB_USER_PACKS as additional read-only roots.
    const home = process.env.HOME || process.env.USERPROFILE || ".";
    return resolve(home, ".bgs-modding-superpowers", "kb", "packs");
}
export function parseUserPackRoots(envValue) {
    if (!envValue)
        return [];
    return envValue
        .split(";")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
}
//# sourceMappingURL=resolve-roots.js.map