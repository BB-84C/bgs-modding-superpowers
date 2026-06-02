import { describe, it, expect } from "vitest";
import { xeditListCapabilitiesTool } from "../../src/tools/list-capabilities.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ctx: ToolContext = {
  sessionId: "sess-LC",
  daemonPid: 1234,
  capabilities: {
    contractVersion: "0.10",
    gameMode: "Fallout4",
    commands: ["system.describe", "records.get", "records.brand_new_thing"],
    fetchedAt: "now",
  },
};

describe("xedit_list_capabilities tool", () => {
  it("returns the curated digest + drift report against live commands", async () => {
    const adapter = makeMockAdapter({});
    const tool = xeditListCapabilitiesTool({ adapter, getContext: () => ctx });
    const env = await tool({});
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    const data = env.data as {
      contractVersion: string;
      groups: unknown[];
      drift: { onlyInDigest: string[]; onlyInLive: string[] };
    };
    expect(data.contractVersion).toBe("0.10");
    expect(data.groups.length).toBeGreaterThan(0);
    expect(data.drift.onlyInLive).toContain("records.brand_new_thing");
    expect(data.drift.onlyInDigest.length).toBeGreaterThan(0);
  });

  it("refuses if session context not yet built", async () => {
    const adapter = makeMockAdapter({});
    const tool = xeditListCapabilitiesTool({ adapter, getContext: () => undefined });
    const env = await tool({});
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("state_violation");
    expect(env.hint).toContain("xedit_session");
  });

  it("emits an audit line when audit logger is wired (carry-forward #2)", async () => {
    const adapter = makeMockAdapter({});
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-listcaps-audit-"));
    const audit = createAuditLogger({ baseDir });
    const tool = xeditListCapabilitiesTool({ adapter, getContext: () => ctx, audit });
    const env = await tool({});
    expect(env.ok).toBe(true);

    const today = new Date().toISOString().slice(0, 10);
    const logPath = join(baseDir, `${today}.jsonl`);
    expect(existsSync(logPath)).toBe(true);
    const lines = readFileSync(logPath, "utf8").trim().split("\n");
    const last = JSON.parse(lines[lines.length - 1]);
    expect(last.tool).toBe("xedit_list_capabilities");
    expect(last.ok).toBe(true);
    expect(last.decision).toBe("ok");
    expect(last.sessionId).toBe("sess-LC");
    expect(last.daemonPid).toBe(1234);
  });
});
