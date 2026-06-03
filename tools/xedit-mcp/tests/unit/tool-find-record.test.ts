import { describe, it, expect } from "vitest";
import { makeFindRecordHandler } from "../../src/tools/find-record.js";
import { defaultRegistry } from "../../src/rules/registry.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ctx: ToolContext = {
  sessionId: "s",
  daemonPid: 1234,
  loadOrder: ["Fallout4.esm", "Patch.esp"],
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("xedit_find_record tool", () => {
  const audit = createAuditLogger({ baseDir: mkdtempSync(join(tmpdir(), "xedit-mcp-find-")) });

  it("by formId returns a slim locator", async () => {
    const adapter = makeMockAdapter({
      "records.find_by_form_id": (args) => ({
        file: args.file,
        formId: args.formId,
        signature: "WEAP",
        editorId: "Foo",
      }),
    });
    const handler = makeFindRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Patch.esp", formId: "0x012345" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data).toMatchObject({
      locators: [{ file: "Patch.esp", formId: "0x012345", signature: "WEAP", editorId: "Foo" }],
    });
  });

  it("LOAD001 fires when file not in load order", async () => {
    const adapter = makeMockAdapter({ "records.find_by_form_id": () => ({}) });
    const handler = makeFindRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Ghost.esp", formId: "0x012345" });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("rule_LOAD001");
  });

  it("by editorId across all loaded files (legacy mock shape: { matches: [...] })", async () => {
    const adapter = makeMockAdapter({
      "records.find_by_editor_id": () => ({
        matches: [{ file: "Patch.esp", formId: "0x0123", signature: "WEAP", editorId: "Foo" }],
      }),
    });
    const handler = makeFindRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ editorId: "Foo" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect((env.data as { locators: unknown[] }).locators).toHaveLength(1);
  });

  it("by editorId unwraps the live daemon shape { hits: [{ locator, object }] }", async () => {
    // Real daemon response shape captured 2026-06-03 from
    // records.find_by_editor_id, observed via xedit_call atomic passthrough:
    //   { truncated, count, hits: [{ locator: {file,formId,path}, object: {...} }] }
    const adapter = makeMockAdapter({
      "records.find_by_editor_id": () => ({
        truncated: false,
        count: 1,
        hits: [
          {
            locator: {
              file: "kinggathcreations_spaceship.esm",
              formId: "2B000810",
              path: "",
            },
            object: {
              kind: "record",
              signature: "QUST",
              formId: "2B000810",
              isMaster: true,
              isDeleted: false,
              isWinningOverride: true,
              overrideCount: 0,
              editorId: "kgcShip_QUST_Manager_Main",
            },
          },
        ],
      }),
    });
    const handler = makeFindRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ editorId: "kgcShip_QUST_Manager_Main", signature: "QUST" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    const locators = (env.data as { locators: Array<Record<string, unknown>> }).locators;
    expect(locators).toHaveLength(1);
    // Identity comes from the daemon locator, not from caller args.
    expect(locators[0].file).toBe("kinggathcreations_spaceship.esm");
    expect(locators[0].formId).toBe("2B000810");
    // editorId comes from the caller (mode B) and round-trips.
    expect(locators[0].editorId).toBe("kgcShip_QUST_Manager_Main");
    // Signature from the object payload is preserved.
    expect(locators[0].signature).toBe("QUST");
  });

  it("does NOT route empty-string file + zero-placeholder formId into formId mode when editorId is provided", async () => {
    // Reproduces the OpenCode envelope reported 2026-06-03 where the client
    // filled every declared property as a placeholder. Before the fix, the
    // handler used `typeof === 'string'` to detect mode A, routed garbage
    // into records.find_by_form_id, then echoed the placeholders back as a
    // fake "found" locator. After the fix, the handler validates each Zod
    // branch strictly, so file:"" fails ByFormId.min(1) and routing falls
    // through to mode B.
    let formIdCalls = 0;
    let editorIdCalls = 0;
    const adapter = makeMockAdapter({
      "records.find_by_form_id": () => {
        formIdCalls += 1;
        return {};
      },
      "records.find_by_editor_id": () => {
        editorIdCalls += 1;
        return {
          hits: [
            {
              locator: { file: "kinggathcreations_spaceship.esm", formId: "2B000810", path: "" },
              object: { signature: "QUST", editorId: "kgcShip_QUST_Manager_Main" },
            },
          ],
        };
      },
    });
    const handler = makeFindRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({
      file: "",
      formId: "00000000",
      editorId: "kgcShip_QUST_Manager_Main",
      signature: "QUST",
    });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(formIdCalls, "must NOT call records.find_by_form_id on empty-file placeholders").toBe(0);
    expect(editorIdCalls, "must route to records.find_by_editor_id").toBe(1);
    const locators = (env.data as { locators: Array<Record<string, unknown>> }).locators;
    expect(locators).toHaveLength(1);
    // Real daemon-provided identity, not the empty-string placeholder echo.
    expect(locators[0].file).toBe("kinggathcreations_spaceship.esm");
    expect(locators[0].formId).toBe("2B000810");
  });

  it("refuses garbage where neither mode validates", async () => {
    const adapter = makeMockAdapter({});
    const handler = makeFindRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    // No editorId, empty file, formId still present → ByFormId fails (empty
    // file), ByEditorId fails (missing editorId). Handler must refuse rather
    // than route into mode A with a placeholder.
    const env = await handler({ file: "", formId: "00000000" });
    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
  });
});
