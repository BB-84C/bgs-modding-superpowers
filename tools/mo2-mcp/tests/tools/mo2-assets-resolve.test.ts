import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _buildCtx(
  sidecarMock?: (m: string, p: unknown) => Promise<unknown>,
): Promise<ToolContext> {
  const root = await mkdtemp(join(tmpdir(), "mo2-ar-"));
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

describe("mo2_assets_resolve", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-assets-resolve.js");
  });

  it("registers as T1", () => {
    expect(getTool("mo2_assets_resolve")?.tier).toBe("T1");
  });

  it("returns sidecar_not_ready without sidecar", async () => {
    const ctx = await _buildCtx();
    const tool = getTool("mo2_assets_resolve")!;
    const result = (await tool.handler({ virtual_path: "Data/foo.dds" }, ctx)) as {
      ok: boolean;
      error?: { code: string };
    };
    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe("sidecar_not_ready");
  });

  it("delegates to sidecar with virtual_path", async () => {
    const captured: Record<string, unknown> = {};
    const ctx = await _buildCtx(async (m, p) => {
      captured.method = m;
      captured.params = p;
      return { virtual_path: "Data/foo.dds", winner: "ModA", providers: ["ModA", "ModB"] };
    });
    const tool = getTool("mo2_assets_resolve")!;
    const result = (await tool.handler({ virtual_path: "Data/foo.dds" }, ctx)) as {
      ok: boolean;
      result: { winner: string };
    };
    expect(captured.method).toBe("assets.resolve_file");
    expect(result.ok).toBe(true);
    expect(result.result.winner).toBe("ModA");
  });
});
