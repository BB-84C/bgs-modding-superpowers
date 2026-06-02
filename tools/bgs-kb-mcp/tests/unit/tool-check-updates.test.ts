import { describe, expect, test } from "vitest";

import type { LoadedPack } from "../../src/discovery/types.js";
import type { PackSession, SessionRegistry } from "../../src/session/types.js";
import { makeCheckUpdatesTool } from "../../src/tools/check-updates.js";
import type { ReleaseIndex } from "../../src/tools/updates/release-index.js";

function loadedPack(packId: string, version: string): LoadedPack {
  return {
    packId,
    displayName: packId,
    version,
    schemaVersion: 1,
    minPluginVersion: "0.2.0",
    root: "bundled",
    rootPath: "/packs",
    packRoot: `/packs/${packId}`,
    kbSqlitePath: `/packs/${packId}/kb.sqlite`,
    manifestPath: `/packs/${packId}/manifest.json`,
    integrityOk: true,
    loadedAt: "2026-06-02T00:00:00.000Z",
    manifest: {
      packId,
      displayName: packId,
      version,
      schemaVersion: 1,
      minPluginVersion: "0.2.0",
      owner: "tests",
      license: "MIT",
      builtAt: "2026-06-02T00:00:00.000Z",
      recordCount: 1,
      domains: ["xedit"],
      games: ["Fallout4"],
      engineFamilies: ["creation-engine"],
      sha256: { "kb.sqlite": "0".repeat(64) },
    },
  };
}

function registry(packs: LoadedPack[]): SessionRegistry {
  const sessions: PackSession[] = packs.map((pack) => ({ pack, all: () => [], get: () => null, close: () => undefined }));
  return {
    get size() {
      return sessions.length;
    },
    byPackId(packId) {
      return sessions.find((session) => session.pack.packId === packId) ?? null;
    },
    all() {
      return sessions.slice();
    },
    forEach(fn) {
      sessions.forEach(fn);
    },
    closeAll() {},
  };
}

function index(entries: Array<Partial<ReleaseIndex["packs"][number]> & { packId: string; version: string }>): ReleaseIndex {
  return {
    releaseTag: "kb-2026.06.02",
    publishedAt: "2026-06-02T00:00:00Z",
    packs: entries.map((entry) => ({
      schemaVersion: 1,
      minPluginVersion: "0.2.0",
      releaseUrl: `https://example.test/${entry.packId}-${entry.version}.zip`,
      sha256: "a".repeat(64),
      sizeBytes: 123,
      ...entry,
    })),
  };
}

describe("bgs_kb_check_updates", () => {
  test("reports upgrade availability from a release index", async () => {
    const tool = makeCheckUpdatesTool({ registry: registry([loadedPack("bgs-kb-core", "2026.06.01")]), currentPluginVersion: "0.2.0", releaseIndexFetcher: async () => index([{ packId: "bgs-kb-core", version: "2026.06.02" }]) });

    const result = await tool({});

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.updates[0]).toMatchObject({ packId: "bgs-kb-core", currentVersion: "2026.06.01", latestVersion: "2026.06.02", upgradeAvailable: true, breakingChange: false });
    }
  });

  test("reports no upgrade when current version equals latest", async () => {
    const tool = makeCheckUpdatesTool({ registry: registry([loadedPack("bgs-kb-core", "2026.06.02")]), currentPluginVersion: "0.2.0", releaseIndexFetcher: async () => index([{ packId: "bgs-kb-core", version: "2026.06.02" }]) });

    const result = await tool({});

    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.updates[0]?.upgradeAvailable).toBe(false);
  });

  test("sets breakingChange when latest pack requires newer plugin", async () => {
    const tool = makeCheckUpdatesTool({ registry: registry([loadedPack("bgs-kb-core", "2026.06.01")]), currentPluginVersion: "0.2.0", releaseIndexFetcher: async () => index([{ packId: "bgs-kb-core", version: "2026.06.02", minPluginVersion: "0.3.0" }]) });

    const result = await tool({});

    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.updates[0]?.breakingChange).toBe(true);
  });

  test("empty registry refuses with not_loaded", async () => {
    const tool = makeCheckUpdatesTool({ registry: registry([]), currentPluginVersion: "0.2.0", releaseIndexFetcher: async () => index([]) });

    const result = await tool({});

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("not_loaded");
  });

  test("network failure returns partial envelope with warning", async () => {
    const tool = makeCheckUpdatesTool({ registry: registry([loadedPack("bgs-kb-core", "2026.06.01")]), currentPluginVersion: "0.2.0", releaseIndexFetcher: async () => { throw new Error("timeout"); } });

    const result = await tool({});

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.status).toBe("partial");
      expect(result.warnings[0]?.code).toBe("release_index_fetch_failed");
      expect(result.data.updates).toEqual([]);
    }
  });

  test("extra args are invalid_request", async () => {
    const tool = makeCheckUpdatesTool({ registry: registry([loadedPack("bgs-kb-core", "2026.06.01")]), currentPluginVersion: "0.2.0", releaseIndexFetcher: async () => index([]) });

    const result = await tool({ surprise: true });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("invalid_request");
  });

  test("packIds filters to the requested subset", async () => {
    const tool = makeCheckUpdatesTool({ registry: registry([loadedPack("bgs-kb-core", "2026.06.01"), loadedPack("bgs-kb-skyrim", "2026.06.01")]), currentPluginVersion: "0.2.0", releaseIndexFetcher: async () => index([{ packId: "bgs-kb-core", version: "2026.06.02" }, { packId: "bgs-kb-skyrim", version: "2026.06.02" }]) });

    const result = await tool({ packIds: ["bgs-kb-skyrim"] });

    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.updates.map((entry) => entry.packId)).toEqual(["bgs-kb-skyrim"]);
  });
});
