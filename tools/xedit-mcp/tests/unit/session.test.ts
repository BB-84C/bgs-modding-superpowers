import { describe, it, expect } from "vitest";
import { buildContext } from "../../src/session.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";

describe("session.buildContext", () => {
  it("populates capabilities + load order from describe/capabilities/files", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4", dataPath: "C:/FO4/Data" }),
      "system.capabilities": () => ({
        contractVersion: "0.10",
        commands: ["records.get", "records.conflict_status"],
        supports: { iKnowWhatImDoing: true },
      }),
      "files.list": () => ({ files: ["Fallout4.esm", "MyPatch.esp"] }),
    });
    const ctx = await buildContext({ adapter, sessionId: "s1" });
    expect(ctx.capabilities?.contractVersion).toBe("0.10");
    expect(ctx.capabilities?.gameMode).toBe("Fallout4");
    expect(ctx.loadOrder).toContain("MyPatch.esp");
    expect(ctx.consentEnabled).toBe(true);
    expect(ctx.sessionId).toBe("s1");
  });

  it("sets consentEnabled=false when capability flag absent", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4", dataPath: "C:/x" }),
      "system.capabilities": () => ({ contractVersion: "0.10", commands: [], supports: {} }),
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
