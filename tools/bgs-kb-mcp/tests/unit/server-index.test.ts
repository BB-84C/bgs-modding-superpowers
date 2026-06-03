import { describe, expect, test } from "vitest";

import { buildServerToolset, jsonResult, TOOL_DEFINITIONS } from "../../src/index.js";
import { ok } from "../../src/envelope/index.js";

describe("KB-2f stdio server entry helpers", () => {
  test("TOOL_DEFINITIONS exposes exactly the stable KB tool names", () => {
    expect(TOOL_DEFINITIONS.map((tool) => tool.name)).toEqual(["bgs_kb_status", "bgs_kb_query", "bgs_kb_get", "bgs_kb_check_updates", "bgs_kb_install_pack"]);
    expect(TOOL_DEFINITIONS).toHaveLength(5);
  });

  test("unknown tool dispatch returns an invalid_request envelope", async () => {
    const toolset = buildServerToolset({
      status: async () => ok({ tool: "bgs_kb_status", summary: "ok", data: {}, status: "completed" }),
      query: async () => ok({ tool: "bgs_kb_query", summary: "ok", data: {}, status: "completed" }),
      get: async () => ok({ tool: "bgs_kb_get", summary: "ok", data: {}, status: "completed" }),
      checkUpdates: async () => ok({ tool: "bgs_kb_check_updates", summary: "ok", data: {}, status: "completed" }),
      installPack: async () => ok({ tool: "bgs_kb_install_pack", summary: "ok", data: {}, status: "completed" }),
    });

    const result = await toolset.invoke("vault_tec_unapproved_experiment", {});

    expect(result.ok).toBe(false);
    expect(result.tool).toBe("vault_tec_unapproved_experiment");
    if (!result.ok) {
      expect(result.code).toBe("invalid_request");
    }
  });

  test("jsonResult wraps a body in MCP text content", () => {
    const body = { ok: true, tool: "bgs_kb_status", data: { packs: [] } };

    expect(jsonResult(body, true)).toEqual({
      content: [{ type: "text", text: JSON.stringify(body) }],
      isError: true,
    });
  });
});
