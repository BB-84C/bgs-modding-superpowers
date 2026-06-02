import { expect, test } from "vitest";

import type { DiscoveryResult, LoadedPack, PackRoot, SkipReason, CollisionReport } from "../../src/discovery/types.js";
import type { SessionRegistry } from "../../src/session/types.js";
import { makeStatusTool } from "../../src/tools/status.js";

const loadedAt = "2026-06-02T00:00:00.000Z";

function pack(packId: string, recordCount: number, root: PackRoot = "bundled", overrides: Partial<LoadedPack> = {}): LoadedPack {
  return {
    packId,
    displayName: `${packId} display`,
    version: "2026.06.02",
    schemaVersion: 1,
    minPluginVersion: "0.2.0",
    root,
    rootPath: `D:/packs/${root}`,
    packRoot: `D:/packs/${root}/${packId}`,
    kbSqlitePath: `D:/packs/${root}/${packId}/kb.sqlite`,
    manifestPath: `D:/packs/${root}/${packId}/manifest.json`,
    manifest: {
      packId,
      displayName: `${packId} display`,
      version: "2026.06.02",
      schemaVersion: 1,
      minPluginVersion: "0.2.0",
      owner: "tests",
      license: "MIT",
      builtAt: loadedAt,
      recordCount,
      domains: ["xedit", "load-order"],
      games: ["Fallout4", "SkyrimSE"],
      engineFamilies: ["creation-engine"],
      sha256: { "kb.sqlite": "a".repeat(64) },
    },
    integrityOk: true,
    loadedAt,
    ...overrides,
  };
}

function discovery(args: { packs?: LoadedPack[]; skipped?: SkipReason[]; collisions?: CollisionReport[] } = {}): DiscoveryResult {
  return {
    packs: args.packs ?? [],
    skipped: args.skipped ?? [],
    collisions: args.collisions ?? [],
    rootsScanned: [
      { root: "bundled", rootPath: "D:/bundled", existed: true },
      { root: "cache", rootPath: "D:/cache", existed: false },
      { root: "user", rootPath: "D:/user-a", existed: true },
      { root: "user", rootPath: "D:/user-b", existed: true },
    ],
    supportedSchemaVersion: 1,
    currentPluginVersion: "0.2.0",
  };
}

function registry(size: number): SessionRegistry {
  return {
    size,
    byPackId: () => null,
    all: () => [],
    forEach: () => undefined,
    closeAll: () => undefined,
  };
}

async function status(dr: DiscoveryResult, registrySize = dr.packs.length) {
  return makeStatusTool({ discovery: dr, registry: registry(registrySize) })({});
}

test("status returns one loaded pack with manifest fields", async () => {
  const env = await status(discovery({ packs: [pack("bgs-kb-core", 46)] }));

  expect(env.ok).toBe(true);
  if (!env.ok) throw new Error("expected ok envelope");
  expect(env.summary).toBe("1 packs loaded (46 records); 0 warnings");
  expect(env.warnings).toEqual([]);
  expect(env.data.totalRecordCount).toBe(46);
  expect(env.data.schemaVersionSupported).toBe(1);
  expect(env.data.cacheRoot).toBe("D:/cache");
  expect(env.data.userPackRoots).toEqual(["D:/user-a", "D:/user-b"]);
  expect(env.data.packs).toEqual([
    {
      packId: "bgs-kb-core",
      displayName: "bgs-kb-core display",
      version: "2026.06.02",
      schemaVersion: 1,
      minPluginVersion: "0.2.0",
      root: "bundled",
      rootPath: "D:/packs/bundled",
      recordCount: 46,
      domains: ["xedit", "load-order"],
      games: ["Fallout4", "SkyrimSE"],
      integrityOk: true,
      loadedAt,
    },
  ]);
});

test("status succeeds with no packs loaded", async () => {
  const env = await status(discovery());

  expect(env.ok).toBe(true);
  if (!env.ok) throw new Error("expected ok envelope");
  expect(env.summary).toBe("0 packs loaded (0 records); 0 warnings");
  expect(env.data.packs).toEqual([]);
  expect(env.data.totalRecordCount).toBe(0);
});

test("status maps missing manifest skips to MEDIUM warnings", async () => {
  const env = await status(discovery({ skipped: [{ code: "missing_manifest", path: "D:/packs/bad", hint: "missing" }] }));

  expect(env.ok).toBe(true);
  if (!env.ok) throw new Error("expected ok envelope");
  expect(env.warnings).toEqual([{ code: "missing_manifest", severity: "MEDIUM", message: "Pack candidate at D:/packs/bad has no manifest.json; skipped" }]);
});

test("status maps integrity failures to HIGH warnings with full hashes", async () => {
  const env = await status(
    discovery({
      skipped: [
        { code: "pack_integrity_failed", path: "D:/packs/tampered", packId: "tampered", expectedSha256: "a".repeat(64), actualSha256: "b".repeat(64) },
      ],
    }),
  );

  expect(env.ok).toBe(true);
  if (!env.ok) throw new Error("expected ok envelope");
  expect(env.warnings[0]).toEqual({
    code: "pack_integrity_failed",
    severity: "HIGH",
    message: `Pack tampered at D:/packs/tampered failed sha256 verification (expected ${"a".repeat(64)}, got ${"b".repeat(64)}); refused`,
  });
});

test("status maps unsupported schema skips to HIGH warnings", async () => {
  const env = await status(discovery({ skipped: [{ code: "schema_version_unsupported", path: "D:/packs/future", packId: "future", packSchemaVersion: 99, supportedSchemaVersion: 1 }] }));

  expect(env.ok).toBe(true);
  if (!env.ok) throw new Error("expected ok envelope");
  expect(env.warnings).toEqual([{ code: "schema_version_unsupported", severity: "HIGH", message: "Pack future requires schemaVersion 99; this plugin supports up to 1" }]);
});

test("status maps min plugin version skips to HIGH warnings", async () => {
  const env = await status(discovery({ skipped: [{ code: "min_plugin_version_unmet", path: "D:/packs/new", packId: "new", required: "9.0.0", current: "0.2.0" }] }));

  expect(env.ok).toBe(true);
  if (!env.ok) throw new Error("expected ok envelope");
  expect(env.warnings).toEqual([{ code: "min_plugin_version_unmet", severity: "HIGH", message: "Pack new requires plugin >= 9.0.0; current is 0.2.0" }]);
});

test("status maps pack collisions to HIGH warnings listing all paths", async () => {
  const env = await status(
    discovery({
      collisions: [
        {
          code: "pack_id_collision",
          packId: "same-pack",
          paths: [
            { root: "bundled", packRoot: "D:/bundled/same" },
            { root: "cache", packRoot: "D:/cache/same" },
          ],
          hint: "remove duplicates",
        },
      ],
    }),
  );

  expect(env.ok).toBe(true);
  if (!env.ok) throw new Error("expected ok envelope");
  expect(env.warnings).toEqual([
    {
      code: "pack_id_collision",
      severity: "HIGH",
      message: "Pack id collision: same-pack present at 2 roots; all refused. Remove duplicates: bundled:D:/bundled/same, cache:D:/cache/same",
    },
  ]);
});

test("status reports multiple skips and collisions in warnings and summary", async () => {
  const env = await status(
    discovery({
      skipped: [
        { code: "missing_manifest", path: "D:/packs/missing", hint: "missing" },
        { code: "invalid_manifest_json", path: "D:/packs/json", hint: "bad json" },
        { code: "missing_kb_sqlite", path: "D:/packs/sqlite", packId: "sqlite" },
      ],
      collisions: [{ code: "pack_id_collision", packId: "dupe", paths: [{ root: "user", packRoot: "D:/user/dupe" }], hint: "remove" }],
    }),
  );

  expect(env.ok).toBe(true);
  if (!env.ok) throw new Error("expected ok envelope");
  expect(env.warnings).toHaveLength(4);
  expect(env.summary).toBe("0 packs loaded (0 records); 4 warnings");
});

test("status warns when discovery and registry sizes differ", async () => {
  const env = await status(discovery({ packs: [pack("a", 1), pack("b", 2)] }), 1);

  expect(env.ok).toBe(true);
  if (!env.ok) throw new Error("expected ok envelope");
  expect(env.warnings).toContainEqual({ code: "internal_inconsistency", severity: "MEDIUM", message: "Internal inconsistency: discovery loaded 2 pack(s), registry has 1 open session(s)" });
});

test("status rejects unexpected args as invalid_request", async () => {
  const env = await makeStatusTool({ discovery: discovery(), registry: registry(0) })({ foo: 1 });

  expect(env.ok).toBe(false);
  if (env.ok) throw new Error("expected refusal");
  expect(env.code).toBe("invalid_request");
});

test("status sums totalRecordCount across all loaded packs", async () => {
  const env = await status(discovery({ packs: [pack("core", 46), pack("cache-pack", 100, "cache"), pack("user-pack", 200, "user")] }));

  expect(env.ok).toBe(true);
  if (!env.ok) throw new Error("expected ok envelope");
  expect(env.data.totalRecordCount).toBe(346);
});
