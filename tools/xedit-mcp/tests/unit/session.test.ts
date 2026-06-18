import { describe, it, expect } from "vitest";
import { buildContext } from "../../src/session.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";

describe("session.buildContext", () => {
  it("populates capabilities + load order from describe/capabilities/files (nested consent path)", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4", dataPath: "C:/FO4/Data" }),
      "system.capabilities": () => ({
        contractVersion: "0.20",
        commands: ["records.get", "records.conflict_status"],
        // r6 nests iKnowWhatImDoing under elementsMutation. Empirically
        // verified against FO4Edit 4.1.6r6: same boolean appears under both
        // `supports.elementsMutation.iKnowWhatImDoing` and
        // `supports.scripts.execution.iKnowWhatImDoing`; never at top level.
        supports: { elementsMutation: { iKnowWhatImDoing: true } },
      }),
      "files.list": () => ({ files: ["Fallout4.esm", "MyPatch.esp"] }),
    });
    const ctx = await buildContext({ adapter, sessionId: "s1" });
    expect(ctx.capabilities?.contractVersion).toBe("0.20");
    expect(ctx.capabilities?.gameMode).toBe("Fallout4");
    expect(ctx.loadOrder).toContain("MyPatch.esp");
    expect(ctx.consentEnabled).toBe(true);
    expect(ctx.sessionId).toBe("s1");
  });

  it("also accepts consent flag at supports.scripts.execution.iKnowWhatImDoing", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4" }),
      "system.capabilities": () => ({
        contractVersion: "0.20",
        commands: [],
        supports: { scripts: { execution: { iKnowWhatImDoing: true } } },
      }),
      "files.list": () => ({ files: [] }),
    });
    const ctx = await buildContext({ adapter, sessionId: "sScripts" });
    expect(ctx.consentEnabled).toBe(true);
  });

  it("IGNORES legacy top-level supports.iKnowWhatImDoing (regression guard for r6 nesting)", async () => {
    // Pre-fix, buildContext read supports.iKnowWhatImDoing at the top level —
    // which never matched the real r6 daemon shape. This test pins the
    // current nesting requirement so a future change cannot silently re-enable
    // the false-positive bug.
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4" }),
      "system.capabilities": () => ({
        contractVersion: "0.20",
        commands: [],
        supports: { iKnowWhatImDoing: true }, // top-level, NOT honored
      }),
      "files.list": () => ({ files: [] }),
    });
    const ctx = await buildContext({ adapter, sessionId: "sLegacy" });
    expect(ctx.consentEnabled).toBe(false);
  });

  it("sets consentEnabled=false when capability flag absent", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4", dataPath: "C:/x" }),
      "system.capabilities": () => ({ contractVersion: "0.20", commands: [], supports: {} }),
      "files.list": () => ({ files: [] }),
    });
    const ctx = await buildContext({ adapter, sessionId: "s2" });
    expect(ctx.consentEnabled).toBe(false);
  });

  it("propagates daemonPid and mcpModeActive when provided", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4" }),
      "system.capabilities": () => ({ contractVersion: "0.10", commands: [], supports: {} }),
      "files.list": () => ({ files: [] }),
    });
    const ctx = await buildContext({ adapter, sessionId: "s3", daemonPid: 1234, mcpModeActive: true });
    expect(ctx.daemonPid).toBe(1234);
    expect(ctx.mcpModeActive).toBe(true);
  });
});
