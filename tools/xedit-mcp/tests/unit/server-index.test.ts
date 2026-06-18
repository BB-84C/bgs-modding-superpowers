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
  test("exposes the stable Batch 1 tool set plus the r6 intent-tool extensions", () => {
    expect(TOOL_DEFINITIONS.map((tool) => tool.name).sort()).toEqual([
      "xedit_call",
      "xedit_create_child_record",
      "xedit_dirty",
      "xedit_find_record",
      "xedit_find_records_by_pattern",
      "xedit_health",
      "xedit_inspect_conflicts",
      "xedit_inspect_conflicts_deep",
      "xedit_list_capabilities",
      "xedit_navigate_ancestry",
      "xedit_read_record",
      "xedit_restart",
      "xedit_session",
      "xedit_start",
      "xedit_status",
      "xedit_stop",
    ]);
    expect(TOOL_DEFINITIONS).toHaveLength(16);
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

  test("xedit_find_record declares both modes' properties with minLength guards and no top-level oneOf/anyOf/allOf/enum/not", () => {
    const tool = TOOL_DEFINITIONS.find((t) => t.name === "xedit_find_record")!;
    const schema = tool.inputSchema as Record<string, unknown> & {
      properties: Record<string, { type: string; minLength?: number; pattern?: string }>;
      required?: string[];
    };
    // Union: handler validates one mode OR the other; no field is unconditionally required.
    expect(Object.keys(schema.properties).sort()).toEqual(["editorId", "file", "formId", "signature"]);
    expect(schema.required ?? []).toEqual([]);

    // minLength guards reject empty-string placeholders at the schema layer.
    expect(schema.properties.file.minLength).toBe(1);
    expect(schema.properties.editorId.minLength).toBe(1);
    expect(schema.properties.formId.pattern).toBe("^(0x)?[0-9a-fA-F]{1,8}$");

    // Top-level oneOf/anyOf/allOf/enum/not are forbidden by OpenAI-style strict
    // tool-schema backends. The handler-side Zod branch validation in
    // src/tools/find-record.ts is the real gate that picks the mode.
    expect(schema.oneOf, "no top-level oneOf").toBeUndefined();
    expect(schema.anyOf, "no top-level anyOf").toBeUndefined();
    expect(schema.allOf, "no top-level allOf").toBeUndefined();
    expect(schema.not, "no top-level not").toBeUndefined();
    expect(schema.enum, "no top-level enum").toBeUndefined();
  });

  test("no tool inputSchema uses forbidden top-level keywords (oneOf/anyOf/allOf/enum/not)", () => {
    // Regression for the OpenAI-style strict tool-schema backend that rejects
    // any top-level union/enum/negation keyword. Catches the next time someone
    // tries the same trick.
    const forbidden = ["oneOf", "anyOf", "allOf", "enum", "not"] as const;
    for (const tool of TOOL_DEFINITIONS) {
      const schema = tool.inputSchema as Record<string, unknown>;
      for (const keyword of forbidden) {
        expect(schema[keyword], `${tool.name}.inputSchema.${keyword} must be undefined`).toBeUndefined();
      }
    }
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

  test("xedit_inspect_conflicts_deep requires file + formId and accepts optional includeReferences boolean", () => {
    const tool = TOOL_DEFINITIONS.find((t) => t.name === "xedit_inspect_conflicts_deep")!;
    const schema = tool.inputSchema as {
      properties: Record<string, { type: string; pattern?: string; minLength?: number }>;
      required: string[];
    };
    expect(Object.keys(schema.properties).sort()).toEqual(["file", "formId", "includeReferences"]);
    expect(schema.required.sort()).toEqual(["file", "formId"]);
    expect(schema.properties.file.minLength).toBe(1);
    expect(schema.properties.formId.pattern).toBe("^(0x)?[0-9a-fA-F]{1,8}$");
    expect(schema.properties.includeReferences.type).toBe("boolean");
  });

  test("xedit_find_records_by_pattern declares the full r6 filter surface with no required fields (refinement is Zod-side)", () => {
    const tool = TOOL_DEFINITIONS.find((t) => t.name === "xedit_find_records_by_pattern")!;
    const schema = tool.inputSchema as {
      properties: Record<string, unknown>;
      required?: string[];
    };
    expect(Object.keys(schema.properties).sort()).toEqual([
      "baseDisplayNameRegex",
      "baseEditorIdRegex",
      "displayNameRegex",
      "displayNamePattern",
      "editorIdPattern",
      "editorIdRegex",
      "file",
      "fullNameRegex",
      "limit",
      "offset",
      "parentFormId",
      "signatures",
    ].sort());
    // No top-level required; at-least-one-predicate is enforced by the Zod
    // refinement inside the handler (handler is the real gate).
    expect(schema.required ?? []).toEqual([]);
  });

  test("xedit_create_child_record requires targetFile + signature + parent, declares the flat parent shape", () => {
    const tool = TOOL_DEFINITIONS.find((t) => t.name === "xedit_create_child_record")!;
    const schema = tool.inputSchema as {
      properties: Record<string, unknown>;
      required: string[];
    };
    expect(Object.keys(schema.properties).sort()).toEqual([
      "editorId",
      "formData",
      "parent",
      "signature",
      "targetFile",
    ]);
    expect(schema.required.sort()).toEqual(["parent", "signature", "targetFile"]);

    const parent = schema.properties.parent as {
      type: string;
      properties: Record<string, unknown>;
      required: string[];
    };
    expect(parent.type).toBe("object");
    expect(Object.keys(parent.properties).sort()).toEqual(["coords", "parentFile", "parentFormId", "subGroup"]);
    expect(parent.required.sort()).toEqual(["parentFile", "parentFormId"]);
    // coords is a [number, number] tuple (no anyOf union).
    const coords = parent.properties.coords as { type: string; minItems: number; maxItems: number };
    expect(coords.type).toBe("array");
    expect(coords.minItems).toBe(2);
    expect(coords.maxItems).toBe(2);
  });

  test("xedit_navigate_ancestry declares both modes flat and lets the handler route", () => {
    const tool = TOOL_DEFINITIONS.find((t) => t.name === "xedit_navigate_ancestry")!;
    const schema = tool.inputSchema as {
      properties: Record<string, { type: string; minLength?: number; pattern?: string }>;
      required?: string[];
    };
    expect(Object.keys(schema.properties).sort()).toEqual(["editorId", "file", "formId", "signature"]);
    expect(schema.required ?? []).toEqual([]);
    expect(schema.properties.file.minLength).toBe(1);
    expect(schema.properties.editorId.minLength).toBe(1);
    expect(schema.properties.formId.pattern).toBe("^(0x)?[0-9a-fA-F]{1,8}$");
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
