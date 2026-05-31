import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { buildServerToolset } from "../../src/index.js";
import { launchDaemon, type LaunchedDaemon } from "../../src/launch.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, "../../../../");
const CLIENT_SCRIPT = resolve(REPO_ROOT, "tools/mo2-vfs-launcher/xedit-client.ps1");
const LAUNCHER_PATH = resolve(
  REPO_ROOT,
  ".artifacts/mo2/Stock Game/Fallout 4/Tools/OpenCodeXEdit/xEdit.exe",
);
const ARTIFACT_DIR = resolve(REPO_ROOT, ".opencode/artifacts/xedit-mcp/acceptance/batch1");
const FIXTURES = resolve(__dirname, "fixtures.json");

const ENABLED = process.env.XEDIT_MCP_INTEGRATION === "1";

describe.runIf(ENABLED)("W2 conflict audit — live daemon", () => {
  let daemon: LaunchedDaemon;
  let toolset: ReturnType<typeof buildServerToolset>;

  beforeAll(async () => {
    daemon = await launchDaemon({
      clientScript: CLIENT_SCRIPT,
      launcherPath: LAUNCHER_PATH,
      gameMode: "Fallout4",
      moProfile: "Default",
    });
    await mkdir(ARTIFACT_DIR, { recursive: true });
    toolset = buildServerToolset({
      adapter: daemon.adapter,
      sessionId: `batch1-${Date.now()}`,
      auditDir: resolve(ARTIFACT_DIR, "audit"),
      daemonPid: daemon.pid,
    });
  }, 240_000);

  afterAll(async () => {
    await daemon?.stop();
  });

  it("xedit_session returns ok with Fallout4 gameMode and a non-empty load order", async () => {
    const env = await toolset.invoke("xedit_session", {});
    await writeFile(resolve(ARTIFACT_DIR, "01-session.json"), JSON.stringify(env, null, 2));
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect((env.data as { gameMode: string }).gameMode).toBe("Fallout4");
    expect((env.data as { loadOrderSize: number }).loadOrderSize).toBeGreaterThan(0);
  });

  it("xedit_list_capabilities reports manageable drift", async () => {
    const env = await toolset.invoke("xedit_list_capabilities", {});
    await writeFile(resolve(ARTIFACT_DIR, "02-capabilities.json"), JSON.stringify(env, null, 2));
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    const drift = (env.data as { drift: { onlyInLive: string[]; onlyInDigest: string[] } }).drift;
    expect(drift.onlyInLive.length + drift.onlyInDigest.length).toBeLessThan(50);
  });

  it("audits the three fixture records end-to-end", async () => {
    const fixtures = JSON.parse(await readFile(FIXTURES, "utf8")) as {
      records: Array<{ file: string; formId: string; expectedVerdict: string; note: string }>;
    };
    const results: unknown[] = [];
    for (const r of fixtures.records) {
      const envInspect = await toolset.invoke("xedit_inspect_conflicts", { file: r.file, formId: r.formId });
      const envRead = await toolset.invoke("xedit_read_record", { file: r.file, formId: r.formId });
      results.push({ fixture: r, inspect: envInspect, read: envRead });
    }
    await writeFile(resolve(ARTIFACT_DIR, "03-audit-results.json"), JSON.stringify(results, null, 2));
    const anyOk = results.some(
      (r) => (r as { inspect: { ok: boolean } }).inspect.ok,
    );
    expect(anyOk).toBe(true);
  });
});
