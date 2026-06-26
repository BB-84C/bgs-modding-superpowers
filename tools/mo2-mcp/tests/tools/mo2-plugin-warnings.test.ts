import { beforeAll, describe, expect, it } from "vitest";
import { zodToJsonSchema } from "zod-to-json-schema";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";

describe("mo2_plugin_warnings", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-plugin-warnings.js");
  });

  it("registers the read-only tool", () => {
    const tool = getTool("mo2_plugin_warnings");
    expect(tool).toBeDefined();
    expect(tool!.tier).toBe("T1");
  });

  it("has an object inputSchema without forbidden top-level union keywords", () => {
    const tool = getTool("mo2_plugin_warnings")!;
    const schema = zodToJsonSchema(tool.inputSchema, { target: "openApi3" }) as Record<string, unknown>;

    expect(schema.type).toBe("object");
    expect((schema as any).anyOf).toBeUndefined();
    expect((schema as any).oneOf).toBeUndefined();
    expect((schema as any).allOf).toBeUndefined();
  });

  it("accepts empty args and non-empty names", () => {
    const schema = getTool("mo2_plugin_warnings")!.inputSchema;

    expect(schema.safeParse({}).success).toBe(true);
    expect(schema.safeParse({ names: ["x.esm"] }).success).toBe(true);
  });

  it("rejects empty names and unknown args", () => {
    const schema = getTool("mo2_plugin_warnings")!.inputSchema;

    expect(schema.safeParse({ names: [""] }).success).toBe(false);
    expect(schema.safeParse({ unknown: 1 }).success).toBe(false);
  });
});
