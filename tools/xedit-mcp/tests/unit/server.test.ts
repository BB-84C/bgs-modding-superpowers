import { describe, it, expect } from "vitest";
import { buildServerToolset } from "../../src/index.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";

describe("MCP server toolset", () => {
  it("registers exactly the Batch 1 tools and dispatches them", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4", dataPath: "C:/x" }),
      "system.capabilities": () => ({
        contractVersion: "0.10", commands: ["records.get"], supports: { iKnowWhatImDoing: true },
      }),
      "files.list": () => ({ files: ["Fallout4.esm", "Patch.esp"] }),
      "session.get_dirty_state": () => ({ dirty: false, dirtyFiles: [], unsavedChangeCount: 0 }),
      "records.get": () => ({ formId: "0x012345", editorId: "Foo" }),
      "records.winning_override": () => ({ file: "Patch.esp", formId: "0x012345" }),
      "records.base_record": () => ({ file: "Fallout4.esm" }),
      "records.conflict_status": () => ({ status: "no_conflict" }),
      "records.referenced_by": () => ({ referencers: [] }),
    });
    const ts = buildServerToolset({ adapter, sessionId: "test", auditDir: undefined });
    expect(ts.list().sort()).toEqual([
      "xedit_call",
      "xedit_create_child_record",
      "xedit_find_record",
      "xedit_find_records_by_pattern",
      "xedit_inspect_conflicts",
      "xedit_inspect_conflicts_deep",
      "xedit_list_capabilities",
      "xedit_navigate_ancestry",
      "xedit_read_record",
      "xedit_session",
    ]);

    const sessionEnv = await ts.invoke("xedit_session", {});
    expect(sessionEnv.ok).toBe(true);

    const readEnv = await ts.invoke("xedit_read_record", { file: "Patch.esp", formId: "0x012345" });
    expect(readEnv.ok).toBe(true);
  });

  it("returns a structured refusal for an unknown tool name", async () => {
    const adapter = makeMockAdapter({});
    const ts = buildServerToolset({ adapter, sessionId: "test", auditDir: undefined });
    const env = await ts.invoke("xedit_nope", {});
    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
  });
});
