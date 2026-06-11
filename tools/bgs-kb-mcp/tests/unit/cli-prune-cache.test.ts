import { existsSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { afterEach, describe, expect, test } from "vitest";

import { cleanupTempPacks, makeTempPack, runCli } from "./test-helpers.js";

afterEach(cleanupTempPacks);

// After the cache-root unification (~/.bgs-modding-superpowers/kb/packs on all
// platforms), tests scope the cache by overriding $HOME / $USERPROFILE so
// defaultCacheRoot() resolves under the temp dir. Both env vars are blanked
// then set to the temp HOME so the resolution order in resolve-roots.ts
// (`HOME ?? USERPROFILE ?? "."`) lands on the temp dir on every OS.
async function makeCacheRoot(): Promise<{
  homeEnv: Record<string, string>;
  cacheRoot: string;
}> {
  const home = await makeTempPack("kb-prune-home-");
  return {
    homeEnv: { HOME: home, USERPROFILE: home, LOCALAPPDATA: "" },
    cacheRoot: join(home, ".bgs-modding-superpowers", "kb", "packs"),
  };
}

async function mkdirp(path: string): Promise<void> {
  await mkdir(path, { recursive: true });
}

describe("cli prune-cache", () => {
  test("keeps current and previous version and removes older versions", async () => {
    const { homeEnv, cacheRoot } = await makeCacheRoot();
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.01"));
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.02"));
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.03"));

    const result = await runCli(["prune-cache"], { env: homeEnv });

    expect(result.code).toBe(0);
    expect(result.stdout).toContain("bgs-kb-core: kept 2026.06.03, 2026.06.02; removed 2026.06.01");
    expect(existsSync(join(cacheRoot, "bgs-kb-core", "2026.06.01"))).toBe(false);
    expect(existsSync(join(cacheRoot, "bgs-kb-core", "2026.06.02"))).toBe(true);
    expect(existsSync(join(cacheRoot, "bgs-kb-core", "2026.06.03"))).toBe(true);
  });

  test("one installed version removes nothing", async () => {
    const { homeEnv, cacheRoot } = await makeCacheRoot();
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.03"));

    const result = await runCli(["prune-cache"], { env: homeEnv });

    expect(result.code).toBe(0);
    expect(result.stdout).toContain("bgs-kb-core: kept 2026.06.03; removed <none>");
  });

  test("empty cache is graceful", async () => {
    const { homeEnv } = await makeCacheRoot();

    const result = await runCli(["prune-cache"], { env: homeEnv });

    expect(result.code).toBe(0);
    expect(result.stdout).toContain("no packs cached");
  });

  test("dry-run reports without deletion", async () => {
    const { homeEnv, cacheRoot } = await makeCacheRoot();
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.01"));
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.02"));
    await mkdirp(join(cacheRoot, "bgs-kb-core", "2026.06.03"));

    const result = await runCli(["prune-cache", "--dry-run"], { env: homeEnv });

    expect(result.code).toBe(0);
    expect(result.stdout).toContain("removed 2026.06.01 (dry-run)");
    expect(existsSync(join(cacheRoot, "bgs-kb-core", "2026.06.01"))).toBe(true);
  });
});
