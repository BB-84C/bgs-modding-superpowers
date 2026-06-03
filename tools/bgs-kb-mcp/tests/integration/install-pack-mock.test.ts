import { createServer, type Server } from "node:http";
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { afterEach, describe, expect, test } from "vitest";

import type { LoadedPack } from "../../src/discovery/types.js";
import type { PackSession, SessionRegistry } from "../../src/session/types.js";
import { makeCheckUpdatesTool } from "../../src/tools/check-updates.js";
import { makeInstallPackTool } from "../../src/tools/install-pack.js";
import { fetchReleaseIndex } from "../../src/tools/updates/release-index.js";
import { cleanupTempPacks, makeTempPack } from "../unit/test-helpers.js";

const integrationEnabled = process.env.BGS_KB_MCP_INTEGRATION === "1";
const loadedAt = "2026-06-02T00:00:00.000Z";
const cleanupServers: Server[] = [];

afterEach(async () => {
  await Promise.all(cleanupServers.splice(0).map((server) => new Promise<void>((resolve) => server.close(() => resolve()))));
  await cleanupTempPacks();
});

function crc32(buf: Buffer): number {
  let crc = 0xffffffff;
  for (const byte of buf) {
    crc ^= byte;
    for (let i = 0; i < 8; i += 1) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function makeZip(entries: Record<string, string>): Buffer {
  const locals: Buffer[] = [];
  const centrals: Buffer[] = [];
  let offset = 0;
  for (const [name, content] of Object.entries(entries)) {
    const nameBuf = Buffer.from(name, "utf8");
    const data = Buffer.from(content, "utf8");
    const crc = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0, 6);
    local.writeUInt16LE(0, 8);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(data.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    locals.push(local, nameBuf, data);

    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(0, 8);
    central.writeUInt16LE(0, 10);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(data.length, 20);
    central.writeUInt32LE(data.length, 24);
    central.writeUInt16LE(nameBuf.length, 28);
    central.writeUInt32LE(offset, 42);
    centrals.push(central, nameBuf);
    offset += local.length + nameBuf.length + data.length;
  }
  const centralStart = offset;
  const centralDir = Buffer.concat(centrals);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(Object.keys(entries).length, 8);
  end.writeUInt16LE(Object.keys(entries).length, 10);
  end.writeUInt32LE(centralDir.length, 12);
  end.writeUInt32LE(centralStart, 16);
  return Buffer.concat([...locals, centralDir, end]);
}

function packManifest(version: string): string {
  return JSON.stringify({ packId: "bgs-kb-core", displayName: "Core", version, schemaVersion: 1, minPluginVersion: "0.2.0", owner: "tests", license: "MIT", builtAt: loadedAt, recordCount: 1, domains: ["xedit"], games: ["Fallout4"], engineFamilies: ["creation-engine"], sha256: { "kb.sqlite": "0".repeat(64) } });
}

async function startFixtureServer(zip: Buffer): Promise<{ baseUrl: string; sha256: string }> {
  const sha256 = createHash("sha256").update(zip).digest("hex");
  const server = createServer((req, res) => {
    const host = `http://127.0.0.1:${(server.address() as { port: number }).port}`;
    if (req.url === "/latest") {
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ tag_name: "kb-test", assets: [{ name: "manifest-index.json", browser_download_url: `${host}/manifest-index.json` }] }));
      return;
    }
    if (req.url === "/manifest-index.json") {
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ releaseTag: "kb-test", publishedAt: loadedAt, packs: [{ packId: "bgs-kb-core", version: "2026.06.02", schemaVersion: 1, minPluginVersion: "0.2.0", releaseUrl: `${host}/bgs-kb-core.zip`, sha256, sizeBytes: zip.length }] }));
      return;
    }
    if (req.url === "/bgs-kb-core.zip") {
      res.setHeader("content-type", "application/zip");
      res.end(zip);
      return;
    }
    res.statusCode = 404;
    res.end("not found");
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  cleanupServers.push(server);
  return { baseUrl: `http://127.0.0.1:${(server.address() as { port: number }).port}`, sha256 };
}

function registry(): SessionRegistry {
  const pack: LoadedPack = {
    packId: "bgs-kb-core",
    displayName: "Core",
    version: "2026.06.01",
    schemaVersion: 1,
    minPluginVersion: "0.2.0",
    root: "bundled",
    rootPath: "/packs",
    packRoot: "/packs/core",
    kbSqlitePath: "/packs/core/kb.sqlite",
    manifestPath: "/packs/core/manifest.json",
    integrityOk: true,
    loadedAt,
    manifest: JSON.parse(packManifest("2026.06.01")),
  };
  const session: PackSession = { pack, all: () => [], get: () => null, close: () => undefined };
  return { size: 1, byPackId: () => session, all: () => [session], forEach: (fn) => fn(session), closeAll: () => undefined };
}

describe.skipIf(!integrationEnabled)("KB-6e mock release install smoke", () => {
  test("check_updates and install_pack work against a local manifest-index + zip", async () => {
    const zip = makeZip({ "manifest.json": packManifest("2026.06.02"), "kb.sqlite": "fixture" });
    const server = await startFixtureServer(zip);
    const cacheRoot = await makeTempPack("kb-install-mock-");
    const releaseIndexFetcher = () => fetchReleaseIndex({ latestReleaseApiUrl: `${server.baseUrl}/latest` });

    const checkUpdates = makeCheckUpdatesTool({ registry: registry(), currentPluginVersion: "0.2.0", releaseIndexFetcher });
    const installPack = makeInstallPackTool({ registry: registry(), cacheRoot, currentPluginVersion: "0.2.0", supportedSchemaVersion: 1, releaseIndexFetcher, tempId: () => "mock" });

    const updateResult = await checkUpdates({});
    expect(updateResult.ok).toBe(true);
    if (updateResult.ok) expect(updateResult.data.updates[0]).toMatchObject({ packId: "bgs-kb-core", latestVersion: "2026.06.02", upgradeAvailable: true });

    const installResult = await installPack({ packId: "bgs-kb-core", version: "2026.06.02" });
    expect(installResult.ok).toBe(true);
    if (installResult.ok) {
      expect(installResult.data.bytesDownloaded).toBe(zip.length);
      expect(installResult.data.sha256Verified).toBe(true);
      expect(existsSync(installResult.data.installed.path)).toBe(true);
      const manifest = JSON.parse(await readFile(join(installResult.data.installed.path, "manifest.json"), "utf8")) as { packId: string; version: string };
      expect(manifest).toMatchObject({ packId: "bgs-kb-core", version: "2026.06.02" });
    }

    await rm(join(cacheRoot, "incoming"), { recursive: true, force: true });
  });
});
