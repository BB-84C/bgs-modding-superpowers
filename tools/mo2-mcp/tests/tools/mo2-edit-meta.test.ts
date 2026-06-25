import { describe, it, expect, beforeAll, beforeEach } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

// Loaded inside beforeAll after _clearToolsForTests + the dynamic
// mo2-edit-meta import; static imports here would evaluate the module first
// and the subsequent dynamic import would return a cached, already-registered
// module that the registry clear has just wiped.
let _resetMetaWriteStaleWarnedForTests: () => void = () => {};

interface FixtureCtx extends ToolContext {
  pipeClient?: {
    call: (method: string, payload: Record<string, unknown>) => Promise<{ ok: boolean; result: unknown; error: { code: string; message: string } | null }>;
    close: () => void;
    discoverAndConnect: () => Promise<void>;
    isConnected: () => boolean;
  };
}

async function _fixture(opts: {
  pipeBehavior?: "absent" | "method_not_found" | "ok" | "real_error";
} = {}): Promise<{ root: string; ctx: FixtureCtx }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-em-"));
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\n[Settings]\nbase_directory=" + root + "\n",
    "utf8",
  );
  await mkdir(join(root, "mods", "ModA"), { recursive: true });
  await writeFile(join(root, "mods", "ModA", "meta.ini"), "[General]\nversion=1.0\n", "utf8");
  const ctx: FixtureCtx = {
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
  } as FixtureCtx;
  if (opts.pipeBehavior && opts.pipeBehavior !== "absent") {
    ctx.pipeClient = {
      call: async () => {
        if (opts.pipeBehavior === "ok") {
          return { ok: true, result: { source: "broker", name: "ModA" }, error: null };
        }
        if (opts.pipeBehavior === "real_error") {
          return {
            ok: false,
            result: null,
            error: { code: "mod_not_found", message: "ModA: not in modList" },
          };
        }
        return {
          ok: false,
          result: null,
          error: { code: "method_not_found", message: "Unsupported method: mods.meta_write" },
        };
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    };
  }
  return { root, ctx };
}

describe("mo2_edit_meta", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    const mod = await import("../../src/tools/mo2-edit-meta.js");
    _resetMetaWriteStaleWarnedForTests = mod._resetMetaWriteStaleWarnedForTests;
  });

  beforeEach(() => {
    _resetMetaWriteStaleWarnedForTests();
  });

  it("registers as T2", () => {
    expect(getTool("mo2_edit_meta")?.tier).toBe("T2");
  });

  it("plan → apply edits multiple sections", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_edit_meta")!;
    const plan = (await tool.handler(
      {
        mode: "plan",
        name: "ModA",
        updates: { General: { version: "2.0" }, Nexus: { nexusID: "42" } },
      },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    expect(plan.ok).toBe(true);

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean };
    expect(apply.ok).toBe(true);

    const meta = await readFile(join(root, "mods", "ModA", "meta.ini"), "utf8");
    expect(meta).toContain("version=2.0");
    expect(meta).toContain("nexusID=42");
  });

  // BUG-23 (issue #12) fix (2026-06-25): stale-broker installs (the deployed
  // mo2_agent_control.py predates the source tree's mods.meta_write handler)
  // would have apply() bomb with `Unsupported method: mods.meta_write`. The
  // fallback path makes apply() degrade to the offline atomic INI rewrite
  // instead of failing, preserving the clean-mutation discipline KB record
  // install-planning.mod-mutation-cleanliness-discipline.v1 even when the
  // broker is the laggard. Real broker errors (mod_not_found, lock
  // contention, etc.) still surface — only method_not_found falls through.
  describe("BUG-23: stale-broker fallback for mods.meta_write", () => {
    it("falls through to offline INI rewrite when broker returns method_not_found", async () => {
      const { root, ctx } = await _fixture({ pipeBehavior: "method_not_found" });
      const tool = getTool("mo2_edit_meta")!;
      const plan = (await tool.handler(
        {
          mode: "plan",
          name: "ModA",
          updates: { General: { comments: "[ARCHIVED 2026-06-25] superseded by ModB" } },
        },
        ctx,
      )) as { ok: boolean; result: { planId: string; lease_token: string } };
      expect(plan.ok).toBe(true);

      const apply = (await tool.handler(
        { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
        ctx,
      )) as { ok: boolean; result: { source: string } };
      expect(apply.ok).toBe(true);
      expect(apply.result.source).toBe("offline_fallback_stale_broker");

      const meta = await readFile(join(root, "mods", "ModA", "meta.ini"), "utf8");
      expect(meta).toContain("comments=[ARCHIVED 2026-06-25] superseded by ModB");
      expect(meta).toContain("version=1.0"); // existing key preserved
    });

    it("surfaces non-method_not_found broker errors (does NOT swallow real failures)", async () => {
      const { ctx } = await _fixture({ pipeBehavior: "real_error" });
      const tool = getTool("mo2_edit_meta")!;
      const plan = (await tool.handler(
        {
          mode: "plan",
          name: "ModA",
          updates: { General: { comments: "test" } },
        },
        ctx,
      )) as { ok: boolean; result: { planId: string; lease_token: string } };
      expect(plan.ok).toBe(true);

      // applyMutation throws on non-method_not_found broker errors; routeToPlanApply
      // does NOT catch (per plan-apply.ts:281 — wrapping happens at the
      // dispatch.ts level, not here). The throw propagating means callers like
      // dispatch.ts see the real failure code instead of a silent "ok: true,
      // source: offline_fallback_stale_broker" answer that would be wrong.
      await expect(
        tool.handler(
          { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
          ctx,
        ),
      ).rejects.toThrow(/ModA: not in modList/);
    });

    it("uses broker result when broker handles the call (source != offline_fallback_stale_broker)", async () => {
      const { ctx } = await _fixture({ pipeBehavior: "ok" });
      const tool = getTool("mo2_edit_meta")!;
      const plan = (await tool.handler(
        {
          mode: "plan",
          name: "ModA",
          updates: { General: { comments: "test" } },
        },
        ctx,
      )) as { ok: boolean; result: { planId: string; lease_token: string } };
      expect(plan.ok).toBe(true);

      const apply = (await tool.handler(
        { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
        ctx,
      )) as { ok: boolean; result: { source: string } };
      expect(apply.ok).toBe(true);
      expect(apply.result.source).toBe("broker");
    });
  });
});
