import { describe, it, expect } from "vitest";
import { xeditSessionTool } from "../../src/tools/session.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const happyMocks = {
  "system.describe": () => ({ gameMode: "Fallout4", dataPath: "C:/x" }),
  "system.capabilities": () => ({
    contractVersion: "0.10",
    commands: ["records.get"],
    // r6 nests iKnowWhatImDoing under elementsMutation; xedit-mcp's
    // buildContext reads from elementsMutation.iKnowWhatImDoing or
    // scripts.execution.iKnowWhatImDoing. Top-level was never the real shape.
    supports: { elementsMutation: { iKnowWhatImDoing: true } },
  }),
  "files.list": () => ({ files: ["Fallout4.esm", "MyPatch.esp"] }),
  "session.get_dirty_state": () => ({ dirtyFiles: [], unsavedChangeCount: 0, dirty: false }),
};

describe("xedit_session tool", () => {
  it("returns an ok envelope with describe + capability summary", async () => {
    const adapter = makeMockAdapter(happyMocks);
    const { tool, getContext } = xeditSessionTool({ adapter, sessionId: "s-test" });
    const env = await tool({});
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data).toMatchObject({
      gameMode: "Fallout4",
      contractVersion: "0.10",
      loadOrderSize: 2,
      consentEnabled: true,
      dirty: false,
    });
    const ctx = getContext();
    expect(ctx?.loadOrder).toContain("MyPatch.esp");
  });

  it("emits an audit line on success when audit logger is wired (carry-forward #2)", async () => {
    const adapter = makeMockAdapter(happyMocks);
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-session-audit-"));
    const audit = createAuditLogger({ baseDir });
    const { tool } = xeditSessionTool({
      adapter,
      sessionId: "sess-123",
      daemonPid: 4242,
      audit,
    });
    const env = await tool({});
    expect(env.ok).toBe(true);

    const today = new Date().toISOString().slice(0, 10);
    const logPath = join(baseDir, `${today}.jsonl`);
    expect(existsSync(logPath)).toBe(true);
    const lines = readFileSync(logPath, "utf8").trim().split("\n");
    expect(lines.length).toBeGreaterThanOrEqual(1);
    const last = JSON.parse(lines[lines.length - 1]);
    expect(last.tool).toBe("xedit_session");
    expect(last.ok).toBe(true);
    expect(last.decision).toBe("ok");
    expect(last.sessionId).toBe("sess-123");
    expect(last.daemonPid).toBe(4242);
  });

  it("emits an audit line on failure", async () => {
    // Adapter that throws → forces the catch path / refusal.
    const adapter = {
      async call(): Promise<never> { throw new Error("daemon down"); },
    };
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-session-audit-err-"));
    const audit = createAuditLogger({ baseDir });
    const { tool } = xeditSessionTool({ adapter, sessionId: "sess-err", audit });
    const env = await tool({});
    expect(env.ok).toBe(false);

    const today = new Date().toISOString().slice(0, 10);
    const lines = readFileSync(join(baseDir, `${today}.jsonl`), "utf8").trim().split("\n");
    const last = JSON.parse(lines[lines.length - 1]);
    expect(last.tool).toBe("xedit_session");
    expect(last.ok).toBe(false);
    expect(last.decision).toBe("refused");
    expect(last.sessionId).toBe("sess-err");
  });
});
