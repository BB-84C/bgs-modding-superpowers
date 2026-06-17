import { describe, it, expect, beforeEach } from "vitest";
import { z } from "zod";
import { FomodChoicesRequiredError, type FomodTreeShape } from "../src/fomod-required-error.js";
import { dispatchToolCall } from "../src/dispatch.js";
import { AuditLogger } from "../src/audit.js";
import { PlanCache } from "../src/plan-apply.js";
import { SnapshotManager } from "../src/snapshot.js";
import { _clearToolsForTests, registerTool } from "../src/tool-registry.js";
import type { Config } from "../src/config.js";
import type { ToolContext } from "../src/types.js";

const sampleTree: FomodTreeShape = {
  fomod_name: "Unique NPCs",
  fomod_version: "2.0",
  pages: [
    {
      name: "Appearance",
      groups: [
        {
          name: "NPC variant",
          type: "SelectExactlyOne",
          options: [
            {
              name: "AIO - Vanilla Hair",
              description: "All-in-one variant using vanilla hair assets.",
              image: "fomod/images/aio.png",
              type: "Recommended",
            },
          ],
        },
      ],
    },
  ],
};

function dispatchCtx(): ToolContext {
  return {
    config: {
      mo2Root: "/tmp/mo2",
      permissionCeiling: "full-control",
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: "/tmp/mo2/.mo2-mcp/snapshots",
      auditRoot: "/tmp/mo2/.mo2-mcp/audit",
    } as Config,
    sessionId: "fomod-required-error-dispatch-test",
    plans: new PlanCache(),
    snapshots: new SnapshotManager("/tmp/mo2/.mo2-mcp/snapshots", "fomod-required-error-dispatch-test"),
    audit: new AuditLogger("/tmp/mo2/.mo2-mcp/audit", "fomod-required-error-dispatch-test"),
  } as unknown as ToolContext;
}

function responseJson(result: Awaited<ReturnType<typeof dispatchToolCall>>): {
  ok: boolean;
  error?: { code: string; message: string; details?: { fomod_tree?: FomodTreeShape } };
} {
  return JSON.parse(result.content[0].text);
}

describe("FomodChoicesRequiredError", () => {
  it("is an Error subclass with stable code + details", () => {
    const err = new FomodChoicesRequiredError({
      code: "fomod_choices_required",
      message: "fomod_choices_required",
      fomod_tree: sampleTree,
    });

    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(FomodChoicesRequiredError);
    expect(err.name).toBe("FomodChoicesRequiredError");
    expect(err.message).toBe("fomod_choices_required");
    expect(err.code).toBe("fomod_choices_required");
    expect(err.details).toEqual({ fomod_tree: sampleTree });
  });
});

describe("dispatch forwards FomodChoicesRequiredError as structured envelope", () => {
  beforeEach(() => {
    _clearToolsForTests();
  });

  it("surfaces code + details.fomod_tree from a thrown FomodChoicesRequiredError", async () => {
    registerTool({
      name: "test_fomod_choices_failing_tool",
      description: "test-only tool that throws a FomodChoicesRequiredError",
      tier: "T0",
      inputSchema: z.object({}),
      handler: async () => {
        throw new FomodChoicesRequiredError({
          code: "fomod_choices_required",
          message: "fomod_choices_required",
          fomod_tree: sampleTree,
        });
      },
    });

    const result = await dispatchToolCall({
      toolName: "test_fomod_choices_failing_tool",
      rawArgs: {},
      ctx: dispatchCtx(),
      rules: [],
    });

    const env = responseJson(result);
    expect(env.ok).toBe(false);
    expect(env.error?.code).toBe("fomod_choices_required");
    expect(env.error?.message).toBe("fomod_choices_required");
    expect(env.error?.details?.fomod_tree).toEqual(sampleTree);
    expect(env.error?.details?.fomod_tree?.pages[0]?.groups[0]?.options[0]?.name).toBe("AIO - Vanilla Hair");
  });

  it("does NOT collapse FomodChoicesRequiredError into internal_error envelope", async () => {
    registerTool({
      name: "test_fomod_choices_reinstall_failing_tool",
      description: "test-only tool that throws a reinstall FomodChoicesRequiredError",
      tier: "T0",
      inputSchema: z.object({}),
      handler: async () => {
        throw new FomodChoicesRequiredError({
          code: "fomod_choices_required_for_reinstall",
          message: "fomod_choices_required_for_reinstall",
          fomod_tree: sampleTree,
        });
      },
    });

    const result = await dispatchToolCall({
      toolName: "test_fomod_choices_reinstall_failing_tool",
      rawArgs: {},
      ctx: dispatchCtx(),
      rules: [],
    });

    const env = responseJson(result);
    expect(env.ok).toBe(false);
    expect(env.error?.code).toBe("fomod_choices_required_for_reinstall");
    expect(env.error?.code).not.toBe("internal_error");
    expect(env.error?.details?.fomod_tree?.pages).toEqual(sampleTree.pages);
  });

  it("still routes plain Error instances into internal_error envelope (no regression for unrelated errors)", async () => {
    registerTool({
      name: "test_plain_error_after_fomod_tool",
      description: "test-only tool that throws a plain Error",
      tier: "T0",
      inputSchema: z.object({}),
      handler: async () => {
        throw new Error("something else went wrong");
      },
    });

    const result = await dispatchToolCall({
      toolName: "test_plain_error_after_fomod_tool",
      rawArgs: {},
      ctx: dispatchCtx(),
      rules: [],
    });

    const env = responseJson(result);
    expect(env.ok).toBe(false);
    expect(env.error?.code).toBe("internal_error");
    expect(env.error?.message).toBe("something else went wrong");
  });
});
