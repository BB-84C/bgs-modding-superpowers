import { describe, it, expect, beforeAll } from "vitest";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { mkdtemp } from "node:fs/promises";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _buildCtx(withSidecar: boolean): Promise<ToolContext> {
  const root = await mkdtemp(join(tmpdir(), "mo2-as-"));
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
  if (withSidecar) {
    // Mock sidecar
    ctx.sidecar = {
      call: async (method: string, _params: unknown) => {
        if (method === "assets.summary") {
          return {
            profile_name: "Default",
            game: "FALLOUT4",
            mod_count: 5,
            enabled_mod_count: 3,
          };
        }
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    } as unknown as ToolContext["sidecar"];
  }
  return ctx;
}

describe("mo2_assets_summary", () => {
  beforeAll(async () => {
    // Clear any state leaked from other files in the same process,
    // then trigger the tool's side-effect registration. ES module
    // imports are cached, so this runs exactly once per file.
    _clearToolsForTests();
    await import("../../src/tools/mo2-assets-summary.js");
  });

  it("registers as T1", () => {
    const tool = getTool("mo2_assets_summary");
    expect(tool).toBeDefined();
    expect(tool!.tier).toBe("T1");
  });

  it("returns sidecar_not_ready when sidecar absent", async () => {
    const ctx = await _buildCtx(false);
    const tool = getTool("mo2_assets_summary")!;
    const result = (await tool.handler({}, ctx)) as { ok: boolean; error?: { code: string } };
    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe("sidecar_not_ready");
  });

  it("delegates to sidecar assets.summary", async () => {
    const ctx = await _buildCtx(true);
    const tool = getTool("mo2_assets_summary")!;
    const result = (await tool.handler({}, ctx)) as {
      ok: boolean;
      result: { game: string; mod_count: number; enabled_mod_count: number };
    };
    expect(result.ok).toBe(true);
    expect(result.result.game).toBe("FALLOUT4");
    expect(result.result.mod_count).toBe(5);
    expect(result.result.enabled_mod_count).toBe(3);
  });
});
