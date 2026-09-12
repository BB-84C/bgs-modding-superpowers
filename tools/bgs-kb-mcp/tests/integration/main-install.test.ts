import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cp, mkdir, mkdtemp, readFile, readdir, symlink, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { afterEach, describe, expect, test } from "vitest";
import { cleanupTempPacks, makeTempPack } from "../unit/test-helpers.js";
import { makeZip } from "../unit/zip-fixture.js";
import type { ReleaseIndex } from "../../src/tools/updates/release-index.js";

const integrationEnabled = process.env.BGS_KB_MCP_INTEGRATION === "1";
const toolRoot = fileURLToPath(new URL("../../", import.meta.url));
const repoRoot = resolve(toolRoot, "../..");
const preload = fileURLToPath(new URL("release-fetch-preload.mjs", import.meta.url));
const hash = (bytes: Buffer) => createHash("sha256").update(bytes).digest("hex");
afterEach(cleanupTempPacks);

async function fixtureRelease(root: string): Promise<string> {
  const source = join(repoRoot, "knowledge/bgs-kb/packs/core");
  const manifestBytes = await readFile(join(source, "manifest.json"));
  const manifest = JSON.parse(manifestBytes.toString());
  const zip = makeZip({ "core/manifest.json": manifestBytes, "core/kb.sqlite": await readFile(join(source, "kb.sqlite")) });
  const releaseDir = join(root, "release");
  await mkdir(releaseDir);
  const releaseUrl = "https://github.com/BB-84C/bgs-modding-superpowers/releases/download/kb-test/core.zip";
  const indexUrl = "https://github.com/BB-84C/bgs-modding-superpowers/releases/download/kb-test/manifest-index.json";
  await writeFile(join(releaseDir, "core.zip"), zip);
  await writeFile(join(releaseDir, "manifest-index.json"), JSON.stringify({ releaseTag: "kb-test", publishedAt: manifest.builtAt, packs: [{ packId: manifest.packId, version: manifest.version, schemaVersion: manifest.schemaVersion, minPluginVersion: manifest.minPluginVersion, releaseUrl, sha256: hash(zip), sizeBytes: zip.length }] }));
  await writeFile(join(releaseDir, "release.json"), JSON.stringify({ tag_name: "kb-test", assets: [{ name: "manifest-index.json", browser_download_url: indexUrl }, { name: "core.zip", browser_download_url: releaseUrl, digest: `sha256:${hash(zip)}` }] }));
  return releaseDir;
}

async function scenario(label: string, mutation?: "dirname" | "discovery", officialDir?: string) {
  // Default suite cleanup uses TEMP; explicit evidence mode keeps copies under
  // the caller's workspace artifact directory for independent readback.
  const evidenceRoot = process.env.BGS_KB_TEST_EVIDENCE_DIR;
  const root = evidenceRoot ? await mkdtemp(join(evidenceRoot, `${label}-`)) : await makeTempPack(`kb-main-${label}-`);
  const runtimeTool = join(root, "tools/bgs-kb-mcp");
  const runtime = join(runtimeTool, "dist");
  await mkdir(runtimeTool, { recursive: true });
  await cp(join(toolRoot, "dist"), runtime, { recursive: true });
  await cp(join(toolRoot, "package.json"), join(runtimeTool, "package.json"));
  await cp(join(repoRoot, "package.json"), join(root, "package.json"));
  await symlink(join(toolRoot, "node_modules"), join(runtimeTool, "node_modules"), "junction");
  // Same actual main()/toolset as production, no bundled pack copy to hide a
  // cache miss. Build is explicit before this suite (not a global pretest).
  const entryPoint = join(runtime, "index.js");
  const originalMain = await readFile(entryPoint, "utf8");
  assert.equal(originalMain, await readFile(join(toolRoot, "dist/index.js"), "utf8"));
  if (mutation) {
    const path = mutation === "dirname" ? entryPoint : join(runtime, "discovery/index.js");
    const source = await readFile(path, "utf8");
    const from = mutation === "dirname" ? "cachePackRoot ? dirname(cachePackRoot) : undefined" : "of await listCandidateDirectories(root))";
    const to = mutation === "dirname" ? "cachePackRoot ? cachePackRoot : undefined" : "of await listPackDirectories(root.rootPath))";
    assert.equal(source.split(from).length, 2, "Mutation must change exactly one known expression");
    await writeFile(path, source.replace(from, to));
  }
  const releaseDir = officialDir ?? await fixtureRelease(root);
  const index = JSON.parse(await readFile(join(releaseDir, "manifest-index.json"), "utf8")) as ReleaseIndex;
  const entry = officialDir ? index.packs.find(pack => pack.packId === "bgs-kb-skyrim")! : index.packs[0];
  const release = JSON.parse(await readFile(join(releaseDir, "release.json"), "utf8"));
  const asset = release.assets.find((asset: { browser_download_url: string }) => asset.browser_download_url === entry.releaseUrl);
  const zip = await readFile(join(releaseDir, asset.name));
  assert.equal(hash(zip), entry.sha256);
  assert.equal(zip.length, entry.sizeBytes);
  assert.equal(asset.digest, `sha256:${hash(zip)}`);
  const home = join(root, "home");
  await mkdir(home);
  const cachePackRoot = join(home, ".bgs-modding-superpowers/kb/packs");
  const expectedInstall = join(cachePackRoot, entry.packId, entry.version);
  const fetchLog = join(root, "fetch.jsonl");
  const env = Object.fromEntries(Object.entries(process.env).filter((pair): pair is [string, string] => pair[1] !== undefined));
  Object.assign(env, { HOME: home, USERPROFILE: home, TEMP: root, TMP: root, BGS_KB_USER_PACKS: "", BGS_KB_TEST_RELEASE_DIR: releaseDir, BGS_KB_TEST_PACK_ID: entry.packId, BGS_KB_TEST_FETCH_LOG: fetchLog });
  const transcript: Array<Record<string, unknown>> = [];
  const exits: Array<{ pid: number | null; exited: boolean }> = [];
  let stage = "initialize";
  let failure: string | undefined;

  async function withServer(work: (call: (name: string, args?: Record<string, unknown>) => Promise<any>) => Promise<void>) {
    const client = new Client({ name: "main-install-regression", version: "1.0.0" }, { capabilities: {} });
    const transport = new StdioClientTransport({ command: process.execPath, args: ["--import", pathToFileURL(preload).href, entryPoint], cwd: root, env, stderr: "pipe" });
    let stderr = "";
    transport.stderr?.on("data", chunk => { stderr += String(chunk); });
    try {
      await client.connect(transport, { timeout: 10000 }); // actual initialize handshake
      transcript.push({ method: "initialize", pid: transport.pid, server: client.getServerVersion() });
      const listed = await client.listTools({}, { timeout: 10000 });
      assert.ok(listed.tools.some(tool => tool.name === "bgs_kb_install_pack"));
      transcript.push({ method: "tools/list", result: listed });
      await work(async (name, args = {}) => {
        const result = await client.callTool({ name, arguments: args }, undefined, { timeout: 10000 });
        const content = result.content as Array<{ type: string; text: string }>;
        const body = JSON.parse(content[0].text);
        transcript.push({ method: "tools/call", name, args, body });
        return body;
      });
    } finally {
      const pid = transport.pid;
      await client.close();
      const deadline = Date.now() + 3000;
      let exited = pid === null;
      while (!exited && Date.now() < deadline) {
        try { process.kill(pid!, 0); } catch { exited = true; break; }
        await new Promise(resolve => setTimeout(resolve, 25));
      }
      exits.push({ pid, exited });
      transcript.push({ stderr });
      assert.ok(exited, "Owned MCP subprocess must exit before next launch");
    }
  }

  try {
    await withServer(async call => {
      const status = await call("bgs_kb_status");
      assert.equal(status.ok, true);
      assert.deepEqual(status.data.packs, []); // no readiness via bundled fallback
      assert.equal(status.data.cacheRoot, cachePackRoot);
      const dry = await call("bgs_kb_install_pack", { packId: entry.packId, version: entry.version, dryRun: true });
      assert.equal(dry.ok, true, JSON.stringify(dry));
      const install = await call("bgs_kb_install_pack", { packId: entry.packId, version: entry.version });
      assert.equal(install.ok, true, JSON.stringify(install));
      stage = "install-path";
      assert.equal(install.data.installed.path, expectedInstall);
      const manifest = JSON.parse(await readFile(join(expectedInstall, "manifest.json"), "utf8"));
      assert.equal(hash(await readFile(join(expectedInstall, "kb.sqlite"))), manifest.sha256["kb.sqlite"]);
      assert.deepEqual(await readdir(join(dirname(cachePackRoot), "incoming")), []);
    });
    stage = "fresh-status";
    await withServer(async call => {
      const status = await call("bgs_kb_status");
      assert.equal(status.ok, true);
      assert.equal(status.data.packs.length, 1);
      assert.equal(status.data.packs[0].packId, entry.packId);
      assert.equal(status.data.packs[0].version, entry.version);
      assert.equal(status.data.packs[0].root, "cache");
      assert.equal(status.data.packs[0].rootPath, cachePackRoot);
      assert.equal(status.data.packs[0].integrityOk, true);
      stage = "query-get";
      const query = await call("bgs_kb_query", { query: "Papyrus", packIds: [entry.packId], maxResults: 3 });
      assert.equal(query.ok, true);
      assert.ok(query.data.hits.length > 0);
      const get = await call("bgs_kb_get", { id: query.data.hits[0].id, packId: entry.packId });
      assert.equal(get.ok, true);
      assert.equal(get.data.record.packId, entry.packId);
      assert.ok(get.data.record.bodyMd.length > 0);
      stage = "complete";
    });
  } catch (error) {
    failure = error instanceof Error ? error.message : String(error);
  }
  const report = { root, mutation, originalMainSha256: hash(Buffer.from(originalMain)), assetSha256: hash(zip), packId: entry.packId, expectedInstall, stage, failure, exits, transcript };
  await writeFile(join(root, "report.json"), JSON.stringify(report, null, 2));
  return report;
}

describe.skipIf(!integrationEnabled)("actual MCP main install and fresh default-cache discovery", () => {
  test("core ZIP installs through actual tool wiring, then fresh MCP status/query/get use the cache", async () => {
    const result = await scenario("core");
    expect(result.failure, JSON.stringify(result)).toBeUndefined();
    expect(result.stage).toBe("complete");
    expect(result.exits).toHaveLength(2);
  }, 45000);

  test.skipIf(!process.env.BGS_KB_TEST_OFFICIAL_RELEASE_DIR)("verified published Skyrim ZIP round-trips through actual MCP main", async () => {
    const result = await scenario("official", undefined, process.env.BGS_KB_TEST_OFFICIAL_RELEASE_DIR);
    expect(result.failure, JSON.stringify(result)).toBeUndefined();
    expect(result.stage).toBe("complete");
    expect(result.exits).toHaveLength(2);
  }, 45000);

  test.each([["dirname", "install-path"], ["discovery", "fresh-status"]] as const)("artifact-only %s mutant is detected at %s", async (mutation, expectedStage) => {
    const result = await scenario(`mutant-${mutation}`, mutation);
    expect(result.failure).toBeDefined();
    expect(result.stage).toBe(expectedStage);
    expect(result.exits.every(exit => exit.exited)).toBe(true);
  }, 45000);
});
