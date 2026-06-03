import { existsSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { afterEach, describe, expect, test } from "vitest";

import { cleanupTempPacks, makeTempPack, runCli } from "./test-helpers.js";

afterEach(cleanupTempPacks);

async function makeCacheRoot(): Promise<{ localAppData: string; cacheRoot: string }> {
  const localAppData = await makeTempPack("kb-prune-localappdata-");
  return { localAppData, cacheRoot: join(localAppData, "bgs-modding-superpowers", "kb", "packs") };
}

async function mkdirp(path: string): Promise<void> {
  await mkdir(path, { recursive: true });
}

describe("cli prune-cache", () => {
  test("keeps current and previous version and removes older versions", async () => {
    const { localAppData, cacheRoot } = await makeCacheRoot();
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.01"));
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.02"));
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.03"));

    const result = await runCli(["prune-cache"], { env: { LOCALAPPDATA: localAppData } });

    expect(result.code).toBe(0);
    expect(result.stdout).toContain("bgs-kb-core: kept 2026.06.03, 2026.06.02; removed 2026.06.01");
    expect(existsSync(join(cacheRoot, "bgs-kb-core", "2026.06.01"))).toBe(false);
    expect(existsSync(join(cacheRoot, "bgs-kb-core", "2026.06.02"))).toBe(true);
    expect(existsSync(join(cacheRoot, "bgs-kb-core", "2026.06.03"))).toBe(true);
  });

  test("one installed version removes nothing", async () => {
    const { localAppData, cacheRoot } = await makeCacheRoot();
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.03"));

    const result = await runCli(["prune-cache"], { env: { LOCALAPPDATA: localAppData } });

    expect(result.code).toBe(0);
    expect(result.stdout).toContain("bgs-kb-core: kept 2026.06.03; removed <none>");
  });

  test("empty cache is graceful", async () => {
    const { localAppData } = await makeCacheRoot();

    const result = await runCli(["prune-cache"], { env: { LOCALAPPDATA: localAppData } });

    expect(result.code).toBe(0);
    expect(result.stdout).toContain("no packs cached");
  });

  test("dry-run reports without deletion", async () => {
    const { localAppData, cacheRoot } = await makeCacheRoot();
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.01"));
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.02"));
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.03"));

    const result = await runCli(["prune-cache", "--dry-run"], { env: { LOCALAPPDATA: localAppData } });

    expect(result.code).toBe(0);
    expect(result.stdout).toContain("removed 2026.06.01 (dry-run)");
    expect(existsSync(join(cacheRoot, "bgs-kb-core", "2026.06.01"))).toBe(true);
  });
});
