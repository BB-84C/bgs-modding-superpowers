import { join } from "node:path";
import { randomUUID } from "node:crypto";

export interface InstallCachePaths {
  incomingRoot: string;
  packsRoot: string;
  zipPath: string;
  extractPath: string;
  targetPath: string;
}

export function resolveInstallCachePaths(cacheRoot: string, packId: string, version: string, tempId: string = randomUUID()): InstallCachePaths {
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
