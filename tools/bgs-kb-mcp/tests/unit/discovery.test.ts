import { createHash } from "node:crypto";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, expect, test } from "vitest";

import { discoverPacks } from "../../src/discovery/index.js";
import type { PackManifest } from "../../src/build/types.js";

const roots: string[] = [];
const loadedAt = "2026-06-02T00:00:00.000Z";

afterEach(async () => {
  for (const root of roots.splice(0)) await rm(root, { recursive: true, force: true });
  delete process.env.BGS_KB_USER_PACKS;
});

async function tempRoot(prefix: string): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), prefix));
  roots.push(root);
  return root;
}

function sha256(data: string | Buffer): string {
  return createHash("sha256").update(data).digest("hex");
}

function manifest(packId: string, sqliteSha: string, overrides: Partial<PackManifest> = {}): PackManifest {
  return {
    packId,
    displayName: `${packId} display`,
    version: "2026.06.02",
    schemaVersion: 1,
    minPluginVersion: "0.1.0",
    owner: "tests",
    license: "MIT",
    builtAt: loadedAt,
    recordCount: 1,
    domains: ["xedit"],
    games: ["Fallout4"],
    engineFamilies: ["creation-engine"],
    sha256: { "kb.sqlite": sqliteSha },
    ...overrides,
  };
}

async function writePack(root: string, dirName: string, options: { packId?: string; sqlite?: Buffer | string; manifest?: Partial<PackManifest>; manifestText?: string; omitManifest?: boolean; omitSqlite?: boolean } = {}): Promise<string> {
  const packRoot = join(root, dirName);
  await mkdir(packRoot, { recursive: true });
  const sqlite = options.sqlite ?? Buffer.alloc(1024, 7);
  if (!options.omitSqlite) await writeFile(join(packRoot, "kb.sqlite"), sqlite);
  if (!options.omitManifest) {
    const body = options.manifestText ?? JSON.stringify(manifest(options.packId ?? dirName, sha256(sqlite), options.manifest), null, 2);
    await writeFile(join(packRoot, "manifest.json"), body, "utf8");
  }
  return packRoot;
}

function now(): Date {
  return new Date(loadedAt);
}

test("discovers one valid bundled pack", async () => {
  const bundledRoot = await tempRoot("kb-discovery-bundled-");
  const packRoot = await writePack(bundledRoot, "bgs-kb-core");

  const result = await discoverPacks({ bundledRoot, cacheRoot: join(bundledRoot, "missing-cache"), userPackRoots: [], currentPluginVersion: "0.1.0", now });

  expect(result.packs).toHaveLength(1);
  expect(result.packs[0]).toMatchObject({ packId: "bgs-kb-core", root: "bundled", rootPath: bundledRoot, packRoot, integrityOk: true, loadedAt });
  expect(result.skipped).toEqual([]);
  expect(result.collisions).toEqual([]);
});

test("skips candidate with missing manifest", async () => {
  const bundledRoot = await tempRoot("kb-discovery-missing-manifest-");
  await writePack(bundledRoot, "missing", { omitManifest: true });

  const result = await discoverPacks({ bundledRoot, cacheRoot: join(bundledRoot, "cache"), userPackRoots: [], now });

  expect(result.packs).toEqual([]);
  expect(result.skipped).toEqual([{ code: "missing_manifest", path: join(bundledRoot, "missing"), hint: "Candidate pack directory is missing manifest.json." }]);
});

test("skips candidate with invalid manifest JSON", async () => {
  const bundledRoot = await tempRoot("kb-discovery-invalid-json-");
  await writePack(bundledRoot, "broken", { manifestText: "{ broken" });

  const result = await discoverPacks({ bundledRoot, cacheRoot: join(bundledRoot, "cache"), userPackRoots: [], now });

  expect(result.packs).toEqual([]);
  expect(result.skipped[0]).toMatchObject({ code: "invalid_manifest_json", path: join(bundledRoot, "broken") });
});

test("enforces schemaVersion gate", async () => {
  const bundledRoot = await tempRoot("kb-discovery-schema-gate-");
  await writePack(bundledRoot, "future", { manifest: { schemaVersion: 99 } });

  const result = await discoverPacks({ bundledRoot, cacheRoot: join(bundledRoot, "cache"), userPackRoots: [], supportedSchemaVersion: 1, now });

  expect(result.packs).toEqual([]);
  expect(result.skipped).toEqual([{ code: "schema_version_unsupported", path: join(bundledRoot, "future"), packId: "future", packSchemaVersion: 99, supportedSchemaVersion: 1 }]);
});

test("enforces minPluginVersion gate", async () => {
  const bundledRoot = await tempRoot("kb-discovery-plugin-gate-");
  await writePack(bundledRoot, "requires-new", { manifest: { minPluginVersion: "9.0.0" } });

  const result = await discoverPacks({ bundledRoot, cacheRoot: join(bundledRoot, "cache"), userPackRoots: [], currentPluginVersion: "0.1.0", now });

  expect(result.packs).toEqual([]);
  expect(result.skipped).toEqual([{ code: "min_plugin_version_unmet", path: join(bundledRoot, "requires-new"), packId: "requires-new", required: "9.0.0", current: "0.1.0" }]);
});

test("refuses integrity-failed packs", async () => {
  const bundledRoot = await tempRoot("kb-discovery-integrity-");
  const sqlite = Buffer.alloc(1024, 8);
  await writePack(bundledRoot, "bad-integrity", { sqlite, manifest: { sha256: { "kb.sqlite": "0".repeat(64) } } });

  const result = await discoverPacks({ bundledRoot, cacheRoot: join(bundledRoot, "cache"), userPackRoots: [], now });

  expect(result.packs).toEqual([]);
  expect(result.skipped).toEqual([{ code: "pack_integrity_failed", path: join(bundledRoot, "bad-integrity"), packId: "bad-integrity", expectedSha256: "0".repeat(64), actualSha256: sha256(sqlite) }]);
});

test("reports collision across bundled and cache roots and refuses both packs", async () => {
  const bundledRoot = await tempRoot("kb-discovery-collide-bundled-");
  const cacheRoot = await tempRoot("kb-discovery-collide-cache-");
  const bundledPack = await writePack(bundledRoot, "bundled-copy", { packId: "same-pack" });
  const cachePack = await writePack(cacheRoot, "cache-copy", { packId: "same-pack" });

  const result = await discoverPacks({ bundledRoot, cacheRoot, userPackRoots: [], now });

  expect(result.packs).toEqual([]);
  expect(result.collisions).toEqual([
    {
      code: "pack_id_collision",
      packId: "same-pack",
      paths: [
        { root: "bundled", packRoot: bundledPack },
        { root: "cache", packRoot: cachePack },
      ],
      hint: "Remove or rename duplicate packs so each packId is unique across discovery roots.",
    },
  ]);
});

test("discovers bundled, cache, and user packs in priority order", async () => {
  const bundledRoot = await tempRoot("kb-discovery-multi-bundled-");
  const cacheRoot = await tempRoot("kb-discovery-multi-cache-");
  const userRoot = await tempRoot("kb-discovery-multi-user-");
  await writePack(bundledRoot, "pack-a");
  await writePack(cacheRoot, "pack-b");
  await writePack(userRoot, "pack-c");

  const result = await discoverPacks({ bundledRoot, cacheRoot, userPackRoots: [userRoot], now });

  expect(result.packs.map((pack) => `${pack.root}:${pack.packId}`)).toEqual(["bundled:pack-a", "cache:pack-b", "user:pack-c"]);
});

test("uses semicolon-separated BGS_KB_USER_PACKS env roots", async () => {
  const bundledRoot = await tempRoot("kb-discovery-env-bundled-");
  const cacheRoot = await tempRoot("kb-discovery-env-cache-");
  const userA = await tempRoot("kb-discovery-env-user-a-");
  const userB = await tempRoot("kb-discovery-env-user-b-");
  process.env.BGS_KB_USER_PACKS = `${userA};${userB}`;

  const result = await discoverPacks({ bundledRoot, cacheRoot, now });

  expect(result.rootsScanned.map((root) => root.rootPath)).toEqual([bundledRoot, cacheRoot, userA, userB]);
});

test("skips packs missing kb.sqlite", async () => {
  const bundledRoot = await tempRoot("kb-discovery-missing-sqlite-");
  await writePack(bundledRoot, "no-sqlite", { omitSqlite: true });

  const result = await discoverPacks({ bundledRoot, cacheRoot: join(bundledRoot, "cache"), userPackRoots: [], now });

  expect(result.packs).toEqual([]);
  expect(result.skipped).toEqual([{ code: "missing_kb_sqlite", path: join(bundledRoot, "no-sqlite"), packId: "no-sqlite" }]);
});
