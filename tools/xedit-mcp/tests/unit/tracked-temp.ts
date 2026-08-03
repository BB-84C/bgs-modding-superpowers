import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll } from "vitest";

declare global {
  var createTrackedTempDirSync: (prefix: string) => string;
}

const tempDirs = new Set<string>();

export function createTrackedTempDirSync(prefix: string): string {
  const path = mkdtempSync(join(tmpdir(), prefix));
  tempDirs.add(path);
  return path;
}

export function cleanupTrackedTempDirs(): void {
  const paths = [...tempDirs];
  tempDirs.clear();
  for (const path of paths) rmSync(path, { recursive: true, force: true });
}

globalThis.createTrackedTempDirSync = createTrackedTempDirSync;
afterAll(() => cleanupTrackedTempDirs());
