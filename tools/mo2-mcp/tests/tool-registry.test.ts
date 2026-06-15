import { describe, it, expect, beforeEach } from "vitest";
import { z } from "zod";
import {
  registerTool,
  getTool,
  getAllTools,
  _clearToolsForTests,
} from "../src/tool-registry.js";

describe("tool registry", () => {
  beforeEach(() => {
    _clearToolsForTests();
  });

  it("starts empty after clear", () => {
    expect(getAllTools()).toEqual([]);
  });

  it("registers and retrieves tools by name", () => {
    registerTool({
      name: "test_tool",
      description: "a test tool",
      inputSchema: z.object({}),
      handler: async () => ({ ok: true }),
      tier: "T1",
    });

    const tool = getTool("test_tool");
    expect(tool).toBeDefined();
    expect(tool!.name).toBe("test_tool");
    expect(getAllTools()).toHaveLength(1);
  });

  it("returns undefined for unknown tool", () => {
    expect(getTool("nonexistent")).toBeUndefined();
  });

  it("supports T1/T2/T3 tier values", () => {
    registerTool({
      name: "t1", description: "x", inputSchema: z.object({}),
      handler: async () => ({}), tier: "T1",
    });
    registerTool({
      name: "t3", description: "y", inputSchema: z.object({}),
      handler: async () => ({}), tier: "T3",
    });
    expect(getAllTools().map(t => t.tier)).toEqual(["T1", "T3"]);
  });
});
