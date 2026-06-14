import { describe, it, expect, beforeAll } from "vitest";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { mkdtemp } from "node:fs/promises";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _buildCtx(
  sidecarMock?: (method: string, params: unknown) => Promise<unknown>,
): Promise<ToolContext> {
  const root = await mkdtemp(join(tmpdir(), "mo2-ac-"));
  const ctx: ToolContext = {
    config: {
      mo2Root: root,
      permissionCeiling: "metadata-editable",
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
      auditRoot: join(root, ".mo2-mcp", "audit"),
    },
    sessionId: "test",
    plans: new PlanCache(),
    snapshots: new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "test"),
    audit: new AuditLogger(join(root, ".mo2-mcp", "audit"), "test"),
  };
  if (sidecarMock) {
    ctx.sidecar = {
      call: sidecarMock,
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    } as unknown as ToolContext["sidecar"];
  }
  return ctx;
}

describe("mo2_assets_conflicts", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-assets-conflicts.js");
  });

  it("registers as T1", () => {
    const tool = getTool("mo2_assets_conflicts");
    expect(tool).toBeDefined();
    expect(tool!.tier).toBe("T1");
  });

  it("returns sidecar_not_ready when sidecar absent", async () => {
    const ctx = await _buildCtx();
    const tool = getTool("mo2_assets_conflicts")!;
    const result = (await tool.handler({ max_results: 10000 }, ctx)) as {
      ok: boolean;
      error?: { code: string };
    };
    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe("sidecar_not_ready");
  });

  it("passes profile_dir + max_results + path_prefix to sidecar", async () => {
    const captured: Record<string, unknown> = {};
    const ctx = await _buildCtx(async (method, params) => {
      captured.method = method;
      captured.params = params;
      return { conflicts: [], total_count: 0, truncated: false };
    });
    const tool = getTool("mo2_assets_conflicts")!;
    await tool.handler({ max_results: 500, path_prefix: "textures/" }, ctx);

    expect(captured.method).toBe("assets.conflicts");
    expect(captured.params).toMatchObject({
      max_results: 500,
      path_prefix: "textures/",
    });
  });

  it("returns sidecar result", async () => {
    const ctx = await _buildCtx(async () => ({
      conflicts: [{ path: "x.dds", providers: ["A", "B"] }],
      total_count: 1,
      truncated: false,
    }));
    const tool = getTool("mo2_assets_conflicts")!;
    const result = (await tool.handler({ max_results: 10000 }, ctx)) as {
      ok: boolean;
      result: { total_count: number; truncated: boolean };
    };
    expect(result.ok).toBe(true);
    expect(result.result.total_count).toBe(1);
    expect(result.result.truncated).toBe(false);
  });
});
