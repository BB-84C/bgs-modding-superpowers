import { describe, expect, test } from "vitest";

import { TOOL_DEFINITIONS } from "../../src/index.js";

// Regression coverage for the OpenCode arg-routing failure mode: when a tool's
// inputSchema lacks explicit `properties` declarations, OpenCode (and many
// model bindings) forward `{}` regardless of what the user wrote. The fix is
// to mirror each Zod schema in `src/tools/*.ts` as an explicit JSON Schema.
// Keep this in lockstep with the Zod schemas; if a Zod schema gains a field,
// add it here and in TOOL_DEFINITIONS in the same commit.
//
// Sibling fix that landed the same rule on bgs-kb-mcp: commit 15adaa7.

describe("xedit-mcp stdio server TOOL_DEFINITIONS", () => {
  test("exposes the stable Batch 1 tool set", () => {
    expect(TOOL_DEFINITIONS.map((tool) => tool.name).sort()).toEqual([
      "xedit_call",
      "xedit_dirty",
      "xedit_find_record",
      "xedit_health",
      "xedit_inspect_conflicts",
      "xedit_list_capabilities",
      "xedit_read_record",
      "xedit_restart",
      "xedit_session",
      "xedit_start",
      "xedit_status",
      "xedit_stop",
    ]);
    expect(TOOL_DEFINITIONS).toHaveLength(12);
  });

  test("every tool inputSchema is an object schema with explicit properties (no loose additionalProperties:true escape)", () => {
    for (const tool of TOOL_DEFINITIONS) {
      const schema = tool.inputSchema as {
        type: string;
        properties: Record<string, unknown>;
        required?: string[];
        additionalProperties?: boolean;
      };
      expect(schema.type, `${tool.name}.inputSchema.type`).toBe("object");
      expect(schema.properties, `${tool.name}.inputSchema.properties`).toBeDefined();
      expect(typeof schema.properties, `${tool.name}.inputSchema.properties is object`).toBe("object");
      expect(schema.additionalProperties, `${tool.name}.inputSchema.additionalProperties`).toBe(false);
    }
  });

  test("no-arg tools declare empty properties", () => {
    const noArgTools = ["xedit_status", "xedit_health", "xedit_dirty", "xedit_session", "xedit_list_capabilities"];
    for (const name of noArgTools) {
      const tool = TOOL_DEFINITIONS.find((t) => t.name === name);
      expect(tool, name).toBeDefined();
      const schema = tool!.inputSchema as { properties: Record<string, unknown> };
      expect(Object.keys(schema.properties), `${name} properties`).toEqual([]);
    }
  });

  test("xedit_start declares the launch override properties without required (all overrides are optional)", () => {
    const tool = TOOL_DEFINITIONS.find((t) => t.name === "xedit_start")!;
    const schema = tool.inputSchema as {
      properties: Record<string, unknown>;
      required?: string[];
    };
    expect(Object.keys(schema.properties).sort()).toEqual(
      ["dataPath", "gameMode", "launcherPath", "moProfile", "moRoot", "pluginsFile"].sort(),
    );
    expect(schema.required ?? []).toEqual([]);
  });

  test("xedit_restart accepts launch overrides plus force flag", () => {
    const tool = TOOL_DEFINITIONS.find((t) => t.name === "xedit_restart")!;
    const schema = tool.inputSchema as { properties: Record<string, unknown> };
    expect(Object.keys(schema.properties).sort()).toEqual(
      ["dataPath", "force", "gameMode", "launcherPath", "moProfile", "moRoot", "pluginsFile"].sort(),
    );
    expect((schema.properties.force as { type: string }).type).toBe("boolean");
  });

  test("xedit_stop accepts a force boolean", () => {
    const tool = TOOL_DEFINITIONS.find((t) => t.name === "xedit_stop")!;
    const schema = tool.inputSchema as { properties: Record<string, unknown> };
    expect(Object.keys(schema.properties)).toEqual(["force"]);
    expect((schema.properties.force as { type: string }).type).toBe("boolean");
  });

  test("xedit_find_record declares the union of formId-mode and editorId-mode as oneOf with minLength guards", () => {
    const tool = TOOL_DEFINITIONS.find((t) => t.name === "xedit_find_record")!;
    const schema = tool.inputSchema as {
      properties: Record<string, { type: string; minLength?: number; pattern?: string }>;
      required?: string[];
      oneOf?: Array<{ required: string[] }>;
    };
    // Union: handler validates one mode OR the other; no field is unconditionally required.
    expect(Object.keys(schema.properties).sort()).toEqual(["editorId", "file", "formId", "signature"]);
    expect(schema.required ?? []).toEqual([]);

    // minLength guards reject empty-string placeholders at the schema layer.
    expect(schema.properties.file.minLength).toBe(1);
    expect(schema.properties.editorId.minLength).toBe(1);
    expect(schema.properties.formId.pattern).toBe("^(0x)?[0-9a-fA-F]{1,8}$");

    // oneOf forces the model/client to pick a single mode instead of filling
    // every declared property as the OpenCode 2026-06-03 repro did.
    expect(schema.oneOf).toBeDefined();
    expect(schema.oneOf).toHaveLength(2);
    const required = schema.oneOf!.map((branch) => branch.required.slice().sort());
    expect(required).toContainEqual(["file", "formId"]);
    expect(required).toContainEqual(["editorId"]);
  });

  test("xedit_read_record requires file + formId", () => {
    const tool = TOOL_DEFINITIONS.find((t) => t.name === "xedit_read_record")!;
    const schema = tool.inputSchema as {
      properties: Record<string, unknown>;
      required: string[];
    };
    expect(Object.keys(schema.properties).sort()).toEqual(["file", "formId"]);
    expect(schema.required.sort()).toEqual(["file", "formId"]);
    expect((schema.properties.formId as { pattern: string }).pattern).toBe("^(0x)?[0-9a-fA-F]{1,8}$");
  });

  test("xedit_inspect_conflicts requires file + formId", () => {
    const tool = TOOL_DEFINITIONS.find((t) => t.name === "xedit_inspect_conflicts")!;
    const schema = tool.inputSchema as {
      properties: Record<string, unknown>;
      required: string[];
    };
    expect(Object.keys(schema.properties).sort()).toEqual(["file", "formId"]);
    expect(schema.required.sort()).toEqual(["file", "formId"]);
  });

  test("xedit_call requires command and exposes args as a pass-through object", () => {
    const tool = TOOL_DEFINITIONS.find((t) => t.name === "xedit_call")!;
    const schema = tool.inputSchema as {
      properties: Record<string, unknown>;
      required: string[];
      additionalProperties: boolean;
    };
    expect(Object.keys(schema.properties).sort()).toEqual(["args", "command"]);
    expect(schema.required).toEqual(["command"]);
    expect(schema.additionalProperties).toBe(false);

    const command = schema.properties.command as { type: string };
    expect(command.type).toBe("string");

    // args is a pass-through object so arbitrary daemon-command args (file, formId,
    // editorId, signature, source, targets, ...) can ride through without the
    // top-level schema needing to enumerate the full daemon command surface.
    const args = schema.properties.args as { type: string; additionalProperties: boolean };
    expect(args.type).toBe("object");
    expect(args.additionalProperties).toBe(true);
  });
});
