import { existsSync } from "node:fs";
import { readdir, rm } from "node:fs/promises";
import { join } from "node:path";

import { compareVersions } from "../tools/updates/semver.js";

export interface PrunePackSummary {
  packId: string;
  kept: string[];
  removed: string[];
}

export interface PruneCacheResult {
  cacheRoot: string;
  dryRun: boolean;
  packs: PrunePackSummary[];
}

async function listDirs(path: string): Promise<string[]> {
  if (!existsSync(path)) return [];
  const entries = await readdir(path, { withFileTypes: true });
  return entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort((a, b) => a.localeCompare(b));
}

export async function pruneCache(cacheRoot: string, opts: { dryRun?: boolean } = {}): Promise<PruneCacheResult> {
  const dryRun = opts.dryRun ?? false;
  const packIds = await listDirs(cacheRoot);
  const packs: PrunePackSummary[] = [];

  for (const packId of packIds) {
    const versions = (await listDirs(join(cacheRoot, packId))).sort((a, b) => compareVersions(b, a));
    const kept = versions.slice(0, 2);
    const removed = versions.slice(2);
    if (!dryRun) {
      for (const version of removed) await rm(join(cacheRoot, packId, version), { recursive: true, force: true });
    }
    packs.push({ packId, kept, removed });
  }

  return { cacheRoot, dryRun, packs };
}

export function formatPruneCacheResult(result: PruneCacheResult): string {
  if (result.packs.length === 0) return `no packs cached at ${result.cacheRoot}\n`;
  return result.packs
    .map((pack) => {
      const kept = pack.kept.length > 0 ? pack.kept.join(", ") : "<none>";
      const removed = pack.removed.length > 0 ? pack.removed.join(", ") : "<none>";
      return `${pack.packId}: kept ${kept}; removed ${removed}${result.dryRun ? " (dry-run)" : ""}`;
    })
    .join("\n") + "\n";
}
