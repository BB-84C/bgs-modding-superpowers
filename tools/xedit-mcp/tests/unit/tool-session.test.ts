import { describe, it, expect } from "vitest";
import { xeditSessionTool } from "../../src/tools/session.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";

describe("xedit_session tool", () => {
  it("returns an ok envelope with describe + capability summary", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4", dataPath: "C:/x" }),
      "system.capabilities": () => ({
        contractVersion: "0.10",
        commands: ["records.get"],
        supports: { iKnowWhatImDoing: true },
      }),
      "files.list": () => ({ files: ["Fallout4.esm", "MyPatch.esp"] }),
      "session.get_dirty_state": () => ({ dirtyFiles: [], unsavedChangeCount: 0, dirty: false }),
    });
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
});
