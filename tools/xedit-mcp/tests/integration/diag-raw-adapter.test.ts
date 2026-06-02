import { describe, it, expect } from "vitest";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createPowershellAdapter } from "../../src/daemon-adapter.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, "../../../../");

const PID = Number.parseInt(process.env.XEDIT_PID ?? "0", 10);
// Diag tests are double-gated: XEDIT_MCP_INTEGRATION=1 enables the integration
// run, BGS_MCP_DIAG=1 enables the ad-hoc diagnostic suite. By default both are
// off and these tests are skipped.
const ENABLED =
  process.env.XEDIT_MCP_INTEGRATION === "1" &&
  process.env.BGS_MCP_DIAG === "1" &&
  PID > 0;

// Client script path resolves to this checkout's tools/mo2-vfs-launcher/ by
// default; override with BGS_TEST_CLIENT_SCRIPT for installs that ship the
// outer client elsewhere.
const CLIENT_SCRIPT =
  process.env.BGS_TEST_CLIENT_SCRIPT ??
  resolve(REPO_ROOT, "tools/mo2-vfs-launcher/xedit-client.ps1");

describe.runIf(ENABLED)("diag — raw adapter call to pre-launched xEdit", () => {
  it("files.list returns the loaded files", async () => {
    const adapter = createPowershellAdapter({
      clientScript: CLIENT_SCRIPT,
      pid: PID,
      pwshExe: "pwsh",
    });
    const res = await adapter.call({ command: "files.list", args: {} });
    // eslint-disable-next-line no-console
    console.log("RAW files.list response:", JSON.stringify(res).slice(0, 2000));
    expect(res.ok).toBe(true);
  }, 30_000);

  it("system.describe returns the game info", async () => {
    const adapter = createPowershellAdapter({
      clientScript: CLIENT_SCRIPT,
      pid: PID,
      pwshExe: "pwsh",
    });
    const res = await adapter.call({ command: "system.describe", args: {} });
    // eslint-disable-next-line no-console
    console.log("RAW system.describe response:", JSON.stringify(res).slice(0, 1000));
    expect(res.ok).toBe(true);
  }, 30_000);
});
