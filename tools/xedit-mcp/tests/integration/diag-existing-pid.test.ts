import { describe, it, expect } from "vitest";
import { createPowershellAdapter } from "../../src/daemon-adapter.js";
import { buildServerToolset } from "../../src/index.js";

const PID = Number.parseInt(process.env.XEDIT_PID ?? "0", 10);
const ENABLED = process.env.XEDIT_MCP_INTEGRATION === "1" && PID > 0;

describe.runIf(ENABLED)("diag — talk to pre-launched xEdit pid via MCP", () => {
  it("xedit_session against an already-loaded daemon reports >0 files", async () => {
    const adapter = createPowershellAdapter({
      clientScript: "D:/awesome-bgs-mod-master/tools/mo2-vfs-launcher/xedit-client.ps1",
      pid: PID,
      pwshExe: "pwsh",
    });
    const ts = buildServerToolset({ adapter, sessionId: "diag", daemonPid: PID });
    const s = await ts.invoke("xedit_session", {});
    // eslint-disable-next-line no-console
    console.log("DIAG session:", JSON.stringify(s, null, 2));
    expect(s.ok).toBe(true);
    if (!s.ok) throw new Error("expected ok");
    expect((s.data as { loadOrderSize: number }).loadOrderSize).toBeGreaterThan(0);

    const f = await ts.invoke("xedit_find_record", { file: "Fallout4.esm", formId: "0x0000003C" });
    // eslint-disable-next-line no-console
    console.log("DIAG find:", JSON.stringify(f, null, 2));
    expect(f.ok).toBe(true);
  }, 30_000);
});
