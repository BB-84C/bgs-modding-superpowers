import { mkdtemp, rm } from "node:fs/promises";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

declare global {
  var createTrackedTempDir: (prefix: string) => Promise<string>;
  var createTrackedTempDirSync: (prefix: string) => string;
}

const tempDirs = new Set<string>();
let installed = false;

export function trackedTempDirs(): string[] {
  return [...tempDirs];
}

export function registerTrackedTempDir(path: string): string {
  tempDirs.add(path);
  return path;
}

export async function createTrackedTempDir(prefix: string): Promise<string> {
  return registerTrackedTempDir(await mkdtemp(join(tmpdir(), prefix)));
}

export function createTrackedTempDirSync(prefix: string): string {
  return registerTrackedTempDir(mkdtempSync(join(tmpdir(), prefix)));
}

export async function cleanupTrackedTempDirs(): Promise<void> {
  const paths = [...tempDirs];
  tempDirs.clear();
  await Promise.all(paths.map((path) => rm(path, { recursive: true, force: true })));
}
