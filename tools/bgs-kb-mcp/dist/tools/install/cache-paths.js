import { join } from "node:path";
import { randomUUID } from "node:crypto";
export function resolveInstallCachePaths(cacheRoot, packId, version, tempId = randomUUID()) {
    const safeStem = `${packId}-${version}-${tempId}`.replace(/[^a-zA-Z0-9._-]/g, "_");
    const incomingRoot = join(cacheRoot, "incoming");
    const packsRoot = join(cacheRoot, "packs");
    return {
        incomingRoot,
        packsRoot,
        zipPath: join(incomingRoot, `${safeStem}.zip`),
        extractPath: join(incomingRoot, safeStem),
        targetPath: join(packsRoot, packId, version),
    };
}
//# sourceMappingURL=cache-paths.js.map