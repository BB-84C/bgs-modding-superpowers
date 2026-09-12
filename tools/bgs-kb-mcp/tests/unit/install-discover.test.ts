import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { cp, readFile, readdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, expect, test, vi } from "vitest";

import type { PackManifest } from "../../src/build/types.js";
import { discoverPacks } from "../../src/discovery/index.js";
import { openSessions } from "../../src/session/index.js";
import { makeInstallPackTool } from "../../src/tools/install-pack.js";
import { makeQueryTool } from "../../src/tools/query.js";
import { cleanupTempPacks, makeTempPack } from "./test-helpers.js";
import { makeZip } from "./zip-fixture.js";

afterEach(async () => {
  vi.unstubAllEnvs();
  await cleanupTempPacks();
});

// Reuse the shipped real pack, including its real SQLite/FTS records. No
// private artifact path or downloaded binary is required to run this suite.
const packRoot = fileURLToPath(new URL("../../../../knowledge/bgs-kb/packs/core/", import.meta.url));
const manifestText = await readFile(join(packRoot, "manifest.json"), "utf8");
const manifest = JSON.parse(manifestText) as PackManifest;
const sqlite = await readFile(join(packRoot, "kb.sqlite"));
const hash = (bytes: Buffer) => createHash("sha256").update(bytes).digest("hex");
const discover = (cacheRoot: string) => discoverPacks({ cacheRoot, bundledRoot: join(cacheRoot, "absent"), userPackRoots: [], currentPluginVersion: "99.0.0", verifyIntegrity: true });
const contents = (prefix = "", overrides = {}) => ({ [`${prefix}manifest.json`]: JSON.stringify({ ...manifest, ...overrides }), [`${prefix}kb.sqlite`]: sqlite });

function installer(cacheRoot: string, entries: Record<string, string | Buffer>, sha?: string) {
  const zip = makeZip(entries);
  return makeInstallPackTool({
    registry: openSessions([]), cacheRoot, currentPluginVersion: "99.0.0", supportedSchemaVersion: 1,
    tempId: () => "roundtrip",
    releaseIndexFetcher: async () => ({ releaseTag: "offline", publishedAt: manifest.builtAt!, packs: [{
      packId: manifest.packId, version: manifest.version, schemaVersion: manifest.schemaVersion,
      minPluginVersion: manifest.minPluginVersion, releaseUrl: "https://example.test/pack.zip", sha256: sha ?? hash(zip), sizeBytes: zip.length,
    }] }),
    fetchImpl: async () => new Response(new Uint8Array(zip)),
  });
}

test.each(["", "core/"])("real ZIP '%s' installs the actual pack root, discovers, and queries after reopening", async (prefix) => {
  const cache = await makeTempPack("kb-roundtrip-");
  // Mirror index.ts: discovery receives the packs root; installer receives
  // its dirname. Never share the installer's root with discovery directly.
  const initial = await discover(join(cache, "packs"));
  const cachePackRoot = initial.rootsScanned.find((root) => root.root === "cache")!.rootPath;
  const tool = installer(dirname(cachePackRoot), contents(prefix));
  const result = await tool({ packId: manifest.packId, version: manifest.version });
  expect(result.ok, JSON.stringify(result)).toBe(true);
  if (!result.ok) return;
  const installed = join(cache, "packs", manifest.packId, manifest.version);
  expect(result.data.installed.path).toBe(installed);
  expect(await readFile(join(installed, "kb.sqlite"))).toEqual(sqlite);
  expect(JSON.parse(await readFile(join(installed, "manifest.json"), "utf8"))).toEqual(manifest);
  expect(await readdir(join(cache, "incoming"))).toEqual([]);
  const found = await discover(cachePackRoot);
  expect(found.skipped).toEqual([]);
  expect(found.packs).toHaveLength(1);
  expect(found.packs[0]).toMatchObject({ packId: manifest.packId, packRoot: installed, integrityOk: true });
  const sessions = openSessions(found.packs);
  try {
    const query = await makeQueryTool({ registry: sessions })({ query: "Papyrus", maxResults: 3 });
    expect(query.ok, JSON.stringify(query)).toBe(true);
    if (query.ok) expect(query.data.hits.length).toBeGreaterThan(0);
  } finally {
    sessions.closeAll();
  }
  // Existing-version policy remains a non-mutating refusal, not an overwrite.
  expect((await tool({ packId: manifest.packId, version: manifest.version })).ok).toBe(false);
  expect(await readFile(join(installed, "kb.sqlite"))).toEqual(sqlite);
});

test("discovers installer versioned paths independently of ZIP installation", async () => {
  const cache = await makeTempPack("kb-versioned-");
  const installed = join(cache, manifest.packId, manifest.version);
  await cp(packRoot, installed, { recursive: true });
  const result = await discover(cache);
  expect(result.packs.map((pack) => pack.packRoot)).toEqual([installed]);
  expect(result.skipped).toEqual([]);
});

test("bundled and user roots stay flat instead of recursively finding version directories", async () => {
  const root = await makeTempPack("kb-flat-roots-");
  for (const name of ["bundled", "user"]) {
    await cp(packRoot, join(root, name, "flat"), { recursive: true });
    await cp(packRoot, join(root, name, "nested", manifest.version), { recursive: true });
  }
  const result = await discoverPacks({ bundledRoot: join(root, "bundled"), userPackRoots: [join(root, "user")], cacheRoot: join(root, "missing"), currentPluginVersion: "99.0.0" });
  expect(result.candidates.map((pack) => pack.packRoot)).toEqual([join(root, "bundled", "flat"), join(root, "user", "flat")]);
  expect(result.skipped.map((item) => item.path)).toEqual([join(root, "bundled", "nested"), join(root, "user", "nested")]);
});

test("flat and multiple versioned copies use existing builtAt precedence, with one logical winner", async () => {
  const cache = await makeTempPack("kb-precedence-");
  const flat = join(cache, "packs", "legacy");
  const newer = join(cache, "packs", manifest.packId, "0.0.1");
  const older = join(cache, "packs", manifest.packId, "99.0.0");
  for (const dest of [flat, newer, older]) await cp(packRoot, dest, { recursive: true });
  await writeFile(join(newer, "manifest.json"), JSON.stringify({ ...manifest, version: "0.0.1", builtAt: "2099-01-01T00:00:00Z" }));
  await writeFile(join(older, "manifest.json"), JSON.stringify({ ...manifest, version: "99.0.0", builtAt: "2000-01-01T00:00:00Z" }));
  // Incoming downloads must never be treated as installed candidates.
  await cp(packRoot, join(cache, "incoming", "unfinished"), { recursive: true });
  const result = await discover(join(cache, "packs"));
  expect(result.packs.map((pack) => pack.packRoot)).toEqual([newer]);
  expect(result.candidates).toHaveLength(3);
  expect(result.collisions).toHaveLength(2);
  expect(result.collisions.every((item) => item.code === "pack_id_overridden")).toBe(true);
  expect(result.skipped).toEqual([]);
});

test.each(["", "core/"])("dryRun '%s' removes all incoming data without publishing", async (prefix) => {
  const cache = await makeTempPack("kb-dry-layout-");
  const result = await installer(cache, contents(prefix))({ packId: manifest.packId, version: manifest.version, dryRun: true });
  expect(result.ok, JSON.stringify(result)).toBe(true);
  expect(existsSync(join(cache, "packs", manifest.packId, manifest.version))).toBe(false);
  expect(await readdir(join(cache, "incoming"))).toEqual([]);
  expect((await discover(join(cache, "packs"))).packs).toEqual([]);
});

test("default HOME cache uses index.ts dirname wiring and is queryable in a fresh process", async () => {
  const home = await makeTempPack("kb-default-home-");
  vi.stubEnv("HOME", home);
  vi.stubEnv("USERPROFILE", home);
  vi.stubEnv("BGS_KB_USER_PACKS", "");
  const initial = await discoverPacks();
  const cachePackRoot = initial.rootsScanned.find((root) => root.root === "cache")!.rootPath;
  expect(cachePackRoot).toBe(join(home, ".bgs-modding-superpowers", "kb", "packs"));
  // This fixture is intentionally newer than bundled core so the existing
  // builtAt precedence selects the cache, rather than hiding a cache miss.
  const result = await installer(dirname(cachePackRoot), contents("core/", { builtAt: "2099-01-01T00:00:00Z" }))({ packId: manifest.packId, version: manifest.version });
  expect(result.ok, JSON.stringify(result)).toBe(true);
  const installed = join(cachePackRoot, manifest.packId, manifest.version);
  const output = execFileSync(process.execPath, ["--input-type=module", "-e", `
    import { discoverPacks } from './dist/discovery/index.js';
    import { openSessions } from './dist/session/index.js';
    import { makeQueryTool } from './dist/tools/query.js';
    const discovery = await discoverPacks();
    const pack = discovery.packs.find(pack => pack.packId === ${JSON.stringify(manifest.packId)});
    const registry = openSessions(discovery.packs);
    try {
      const query = await makeQueryTool({registry})({query: 'Papyrus', packIds: [${JSON.stringify(manifest.packId)}], maxResults: 3});
      console.log(JSON.stringify({packRoot: pack?.packRoot, root: pack?.root, query}));
    } finally { registry.closeAll(); }
  `], { encoding: "utf8", env: process.env, timeout: 15000 });
  const readback = JSON.parse(output);
  expect(readback.packRoot).toBe(installed);
  expect(readback.root).toBe("cache");
  expect(readback.query.ok).toBe(true);
  expect(readback.query.data.hits.length).toBeGreaterThan(0);
});

test.each([
  ["missing manifest", { "kb.sqlite": sqlite }],
  ["too deeply wrapped", contents("outer/core/")],
  ["two wrappers", { ...contents("one/"), ...contents("two/") }],
  ["root and wrapper", { ...contents(), ...contents("core/") }],
  ["malformed manifest", { ...contents("core/"), "core/manifest.json": "{" }],
  ["wrong identity", contents("core/", { packId: "wrong-pack" })],
  ["wrong version", contents("core/", { version: "0.0.0" })],
  ["unsafe ZIP path", { ...contents("core/"), "../escape.txt": "not allowed" }],
] satisfies Array<[string, Record<string, string | Buffer>]>)("invalid layout: %s refuses without publication and cleans incoming", async (_name, entries) => {
  const cache = await makeTempPack("kb-invalid-layout-");
  const result = await installer(cache, entries)({ packId: manifest.packId, version: manifest.version });
  expect(result.ok, JSON.stringify(result)).toBe(false);
  expect(existsSync(join(cache, "packs", manifest.packId, manifest.version))).toBe(false);
  expect(await readdir(join(cache, "incoming"))).toEqual([]);
  expect(existsSync(join(cache, "incoming", "escape.txt"))).toBe(false);
});

test.each([
  ["schema_version_unsupported", contents("core/", { schemaVersion: 999 }), undefined],
  ["min_plugin_version_unmet", contents("core/", { minPluginVersion: "999.0.0" }), undefined],
  ["pack_integrity_failed", contents("core/"), "0".repeat(64)],
] as const)("wrapped ZIP preserves %s validation and cleanup", async (code, entries, sha) => {
  const cache = await makeTempPack("kb-layout-gate-");
  const result = await installer(cache, entries, sha)({ packId: manifest.packId, version: manifest.version });
  expect(result.ok).toBe(false);
  if (!result.ok) expect(result.code).toBe(code);
  expect(existsSync(join(cache, "packs", manifest.packId, manifest.version))).toBe(false);
  expect(await readdir(join(cache, "incoming"))).toEqual([]);
});
