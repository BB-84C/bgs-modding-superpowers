import { describe, expect, it, beforeAll } from "vitest";
import { join } from "node:path";
import { mkdtemp, readdir, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { z } from "zod";
import { _clearToolsForTests, getTool } from "../../src/tool-registry.js";
import { BindingManager, type BindingManagerOptions } from "../../src/binding.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import { dispatchToolCall } from "../../src/dispatch.js";
import type { Config, RawConfig } from "../../src/config.js";
import type { ToolContext } from "../../src/types.js";

function configFor(root: string, profile = "Default"): Config {
  return {
    mo2Root: root,
    permissionCeiling: "metadata-editable" as RawConfig["permission_ceiling"],
    allowedProfiles: [profile],
    deny: [],
    snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
    auditRoot: join(root, ".mo2-mcp", "audit"),
  };
}

function bindingOpts(): BindingManagerOptions {
  return {
    loadConfig: async ({ mo2Root }) => configFor(mo2Root),
    readMoIni: async () => ({
      general: { game: "fallout4", gameName: "Fallout 4", gamePath: "C:/Games/Fallout4" },
      settings: { modDirectory: "C:/MO2/mods" },
    }),
    detectMo2Running: async () => ({
      processRunning: false,
      sharedMemoryPresent: false,
      profileLockHeld: false,
      online: false,
      confidence: "low",
    }),
    createSidecarClient: () => ({
      async start() {},
      async stop() {},
      isReady: () => true,
    }) as never,
    createPipeClient: () => ({
      async discoverAndConnect() {},
      close() {},
      isConnected: () => false,
    }) as never,
    log: () => {},
  };
}

async function makeCtx(): Promise<ToolContext> {
  const root = await mkdtemp(join(tmpdir(), "mo2-session-"));
  return {
    binding: new BindingManager(bindingOpts()),
    sessionId: "session-test",
    plans: new PlanCache(),
    snapshots: new SnapshotManager(join(root, "snapshots"), "session-test"),
    audit: new AuditLogger(join(root, "audit"), "session-test"),
  };
}

function responseJson(result: { content: Array<{ type: "text"; text: string }> }): unknown {
  return JSON.parse(result.content[0].text) as unknown;
}

describe("mo2_session", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-session.js");
  });

  it("registers as a T1 lifecycle tool", () => {
    const tool = getTool("mo2_session");
    expect(tool).toBeDefined();
    expect(tool!.tier).toBe("T1");
  });

  it("returns a read-only snapshot when called with no args", async () => {
    const ctx = await makeCtx();
    const tool = getTool("mo2_session")!;

    const result = await tool.handler({}, ctx);

    expect(result).toEqual({ ok: true, snapshot: { state: "unbound" } });
  });

  it("binds when called with mo2Root and profile", async () => {
    const ctx = await makeCtx();
    const tool = getTool("mo2_session")!;

    const result = await tool.handler({ mo2Root: "C:/MO2", profile: "ProfileB" }, ctx);

    expect(result).toMatchObject({
      ok: true,
      snapshot: { state: "bound", mo2Root: "C:/MO2", profile: "ProfileB" },
    });
    expect(ctx.binding.requireBound().config.allowedProfiles[0]).toBe("ProfileB");
  });

  it("unbinds when called with unbind true", async () => {
    const ctx = await makeCtx();
    const tool = getTool("mo2_session")!;
    await tool.handler({ mo2Root: "C:/MO2" }, ctx);

    const result = await tool.handler({ unbind: true }, ctx);

    expect(result).toEqual({ ok: true, snapshot: { state: "unbound" } });
  });

  it("is audit-logged through central dispatch", async () => {
    const root = await mkdtemp(join(tmpdir(), "mo2-session-audit-"));
    const ctx: ToolContext = {
      binding: new BindingManager(bindingOpts()),
      sessionId: "audit-session",
      plans: new PlanCache(),
      snapshots: new SnapshotManager(join(root, "snapshots"), "audit-session"),
      audit: new AuditLogger(join(root, "audit"), "audit-session"),
    };
    const passthroughRule = {
      id: "PASS",
      severity: "MEDIUM" as const,
      appliesTo: () => true,
      evaluate: async () => null,
    };

    const result = await dispatchToolCall({
      toolName: "mo2_session",
      rawArgs: {},
      ctx,
      rules: [passthroughRule],
    });

    expect(responseJson(result)).toEqual({ ok: true, snapshot: { state: "unbound" } });
    const files = await readdir(join(root, "audit"));
    const line = (await readFile(join(root, "audit", files[0]), "utf8")).trim();
    expect(JSON.parse(line)).toMatchObject({ tool: "mo2_session", decision: "ok" });
  });

  it("rejects invalid shapes via schema", async () => {
    const tool = getTool("mo2_session")!;
    expect(tool.inputSchema).toBeInstanceOf(z.ZodType);
    expect(tool.inputSchema.safeParse({ mo2Root: 123 }).success).toBe(false);
  });
});
