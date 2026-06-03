import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdir, readdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { afterEach, describe, expect, test } from "vitest";

import type { SessionRegistry } from "../../src/session/types.js";
import { makeInstallPackTool } from "../../src/tools/install-pack.js";
import type { ReleaseIndex } from "../../src/tools/updates/release-index.js";
import { cleanupTempPacks, makeTempPack } from "./test-helpers.js";

afterEach(cleanupTempPacks);

const zipBytes = new TextEncoder().encode("fixture zip bytes");
const zipSha = createHash("sha256").update(zipBytes).digest("hex");

const registry: SessionRegistry = { size: 0, byPackId: () => null, all: () => [], forEach: () => undefined, closeAll: () => undefined };

function releaseIndex(overrides: Partial<ReleaseIndex["packs"][number]> = {}): ReleaseIndex {
  return {
    releaseTag: "kb-test",
    publishedAt: "2026-06-02T00:00:00Z",
    packs: [
      {
        packId: "bgs-kb-skyrim",
        version: "2026.06.02",
        schemaVersion: 1,
        minPluginVersion: "0.2.0",
        releaseUrl: "https://example.test/bgs-kb-skyrim.zip",
        sha256: zipSha,
        sizeBytes: zipBytes.byteLength,
        ...overrides,
      },
    ],
  };
}

function fetchOk(body: Uint8Array = zipBytes): typeof fetch {
  return async () => new Response(new Uint8Array(body), { status: 200 });
}

async function writeManifest(dest: string, manifestOverrides: Record<string, unknown> = {}): Promise<void> {
  await mkdir(dest, { recursive: true });
  await writeFile(
    join(dest, "manifest.json"),
    JSON.stringify({ packId: "bgs-kb-skyrim", displayName: "Skyrim", version: "2026.06.02", schemaVersion: 1, minPluginVersion: "0.2.0", owner: "tests", license: "MIT", builtAt: "2026-06-02T00:00:00Z", recordCount: 0, domains: [], games: [], engineFamilies: [], sha256: { "kb.sqlite": "0".repeat(64) }, ...manifestOverrides }),
    "utf8",
  );
}

describe("bgs_kb_install_pack", () => {
  test("installs a verified downloaded pack into cache", async () => {
    const cacheRoot = await makeTempPack("kb-install-");
    const tool = makeInstallPackTool({ registry, cacheRoot, currentPluginVersion: "0.2.0", supportedSchemaVersion: 1, releaseIndexFetcher: async () => releaseIndex(), fetchImpl: fetchOk(), extractZipImpl: async (_zip, dest) => writeManifest(dest), tempId: () => "happy" });

    const result = await tool({ packId: "bgs-kb-skyrim", version: "2026.06.02" });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.sha256Verified).toBe(true);
      expect(result.data.bytesDownloaded).toBe(zipBytes.byteLength);
      expect(existsSync(result.data.installed.path)).toBe(true);
      expect(existsSync(join(cacheRoot, "incoming", "bgs-kb-skyrim-2026.06.02-happy.zip"))).toBe(false);
    }
  });

  test("dryRun verifies the payload without moving into packs", async () => {
    const cacheRoot = await makeTempPack("kb-install-dry-");
    const tool = makeInstallPackTool({ registry, cacheRoot, currentPluginVersion: "0.2.0", supportedSchemaVersion: 1, releaseIndexFetcher: async () => releaseIndex(), fetchImpl: fetchOk(), extractZipImpl: async (_zip, dest) => writeManifest(dest), tempId: () => "dry" });

    const result = await tool({ packId: "bgs-kb-skyrim", version: "2026.06.02", dryRun: true });

    expect(result.ok).toBe(true);
    if (result.ok) expect(existsSync(result.data.installed.path)).toBe(false);
  });

  test("sha256 mismatch refuses and cleans incoming files", async () => {
    const cacheRoot = await makeTempPack("kb-install-badsha-");
    const tool = makeInstallPackTool({ registry, cacheRoot, currentPluginVersion: "0.2.0", supportedSchemaVersion: 1, releaseIndexFetcher: async () => releaseIndex({ sha256: "f".repeat(64) }), fetchImpl: fetchOk(), extractZipImpl: async (_zip, dest) => writeManifest(dest), tempId: () => "badsha" });

    const result = await tool({ packId: "bgs-kb-skyrim", version: "2026.06.02" });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("pack_integrity_failed");
    expect(existsSync(join(cacheRoot, "incoming", "bgs-kb-skyrim-2026.06.02-badsha.zip"))).toBe(false);
  });

  test("schemaVersion gate failure refuses", async () => {
    const cacheRoot = await makeTempPack("kb-install-schema-");
    const tool = makeInstallPackTool({ registry, cacheRoot, currentPluginVersion: "0.2.0", supportedSchemaVersion: 1, releaseIndexFetcher: async () => releaseIndex(), fetchImpl: fetchOk(), extractZipImpl: async (_zip, dest) => writeManifest(dest, { schemaVersion: 2 }), tempId: () => "schema" });

    const result = await tool({ packId: "bgs-kb-skyrim", version: "2026.06.02" });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("schema_version_unsupported");
  });

  test("minPluginVersion gate failure refuses", async () => {
    const cacheRoot = await makeTempPack("kb-install-min-");
    const tool = makeInstallPackTool({ registry, cacheRoot, currentPluginVersion: "0.2.0", supportedSchemaVersion: 1, releaseIndexFetcher: async () => releaseIndex(), fetchImpl: fetchOk(), extractZipImpl: async (_zip, dest) => writeManifest(dest, { minPluginVersion: "0.3.0" }), tempId: () => "min" });

    const result = await tool({ packId: "bgs-kb-skyrim", version: "2026.06.02" });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("min_plugin_version_unmet");
  });

  test("network failure maps to download_failed", async () => {
    const cacheRoot = await makeTempPack("kb-install-net-");
    const tool = makeInstallPackTool({ registry, cacheRoot, currentPluginVersion: "0.2.0", supportedSchemaVersion: 1, releaseIndexFetcher: async () => releaseIndex(), fetchImpl: async () => { throw new Error("offline"); }, extractZipImpl: async (_zip, dest) => writeManifest(dest), tempId: () => "net" });

    const result = await tool({ packId: "bgs-kb-skyrim", version: "2026.06.02" });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("download_failed");
  });

  test("target version already installed refuses without overwrite", async () => {
    const cacheRoot = await makeTempPack("kb-install-existing-");
    await mkdir(join(cacheRoot, "packs", "bgs-kb-skyrim", "2026.06.02"), { recursive: true });
    const tool = makeInstallPackTool({ registry, cacheRoot, currentPluginVersion: "0.2.0", supportedSchemaVersion: 1, releaseIndexFetcher: async () => releaseIndex(), fetchImpl: fetchOk(), extractZipImpl: async (_zip, dest) => writeManifest(dest), tempId: () => "existing" });

    const result = await tool({ packId: "bgs-kb-skyrim", version: "2026.06.02" });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("download_failed");
  });

  test("incoming extraction is cleaned up on failure", async () => {
    const cacheRoot = await makeTempPack("kb-install-clean-");
    const tool = makeInstallPackTool({ registry, cacheRoot, currentPluginVersion: "0.2.0", supportedSchemaVersion: 1, releaseIndexFetcher: async () => releaseIndex(), fetchImpl: fetchOk(), extractZipImpl: async (_zip, dest) => { await writeManifest(dest, { schemaVersion: 2 }); }, tempId: () => "clean" });

    await tool({ packId: "bgs-kb-skyrim", version: "2026.06.02" });

    const incoming = join(cacheRoot, "incoming");
    expect(existsSync(incoming) ? await readdir(incoming) : []).toEqual([]);
  });
});
