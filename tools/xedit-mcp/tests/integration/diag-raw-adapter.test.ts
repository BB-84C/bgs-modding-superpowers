import { describe, it, expect } from "vitest";
import { createPowershellAdapter } from "../../src/daemon-adapter.js";

const PID = Number.parseInt(process.env.XEDIT_PID ?? "0", 10);
const ENABLED = process.env.XEDIT_MCP_INTEGRATION === "1" && PID > 0;

describe.runIf(ENABLED)("diag — raw adapter call to pre-launched xEdit", () => {
  it("files.list returns the loaded files", async () => {
    const adapter = createPowershellAdapter({
      clientScript: "D:/awesome-bgs-mod-master/tools/mo2-vfs-launcher/xedit-client.ps1",
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
      clientScript: "D:/awesome-bgs-mod-master/tools/mo2-vfs-launcher/xedit-client.ps1",
      pid: PID,
      pwshExe: "pwsh",
    });
    const res = await adapter.call({ command: "system.describe", args: {} });
    // eslint-disable-next-line no-console
    console.log("RAW system.describe response:", JSON.stringify(res).slice(0, 1000));
    expect(res.ok).toBe(true);
  }, 30_000);
});
