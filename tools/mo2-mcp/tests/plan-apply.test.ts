import { describe, it, expect, beforeEach, vi } from "vitest";
import { mkdtemp, writeFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import {
  PlanCache,
  runPlanMode,
  runApplyMode,
  routeToPlanApply,
  type PlanApplyHandler,
} from "../src/plan-apply.js";
import { SnapshotManager } from "../src/snapshot.js";
import { AuditLogger } from "../src/audit.js";
import type { ToolContext } from "../src/types.js";
import {
  acquireLeasesForTargets,
  releaseLeaseLocks,
} from "../src/lease-lock.js";

const stubCtx = {
  config: {
    mo2Root: "/tmp",
    permissionCeiling: "metadata-editable" as const,
    allowedProfiles: ["Default"],
    deny: [],
    snapshotRoot: "/tmp/.mo2-mcp/snapshots",
    auditRoot: "/tmp/.mo2-mcp/audit",
  },
  sessionId: "test-session",
  plans: new PlanCache(),
  snapshots: new SnapshotManager("/tmp/.mo2-mcp/snapshots", "test-session"),
  audit: new AuditLogger("/tmp/.mo2-mcp/audit", "test-session"),
} satisfies ToolContext;

describe("PlanCache", () => {
  it("stores and retrieves plans by id", () => {
    const c = new PlanCache();
    const rec = c.store({
      tool: "x",
      args: {},
      diff: "d",
      affectedFiles: [],
      lease: { token: "t", components: [] },
      leaseLockTargetHashes: ["h"],
    });
    expect(c.get(rec.planId)?.tool).toBe("x");
  });

  it("returns null for unknown plan id", () => {
    const c = new PlanCache();
    expect(c.get("unknown")).toBeNull();
  });

  it("consume removes the plan", () => {
    const c = new PlanCache();
    const rec = c.store({
      tool: "x",
      args: {},
      diff: "d",
      affectedFiles: [],
      lease: { token: "t", components: [] },
      leaseLockTargetHashes: ["h"],
    });
    expect(c.consume(rec.planId)).not.toBeNull();
    expect(c.get(rec.planId)).toBeNull();
  });

  it("expires plans after TTL", () => {
    const c = new PlanCache();
    const rec = c.store({
      tool: "x",
      args: {},
      diff: "d",
      affectedFiles: [],
      lease: { token: "t", components: [] },
      leaseLockTargetHashes: ["h"],
      ttlMs: -1, // already expired
    });
    expect(c.get(rec.planId)).toBeNull();
  });
});

describe("runPlanMode + runApplyMode", () => {
  it("takes snapshot during apply after lease verification, not during plan", async () => {
    const root = await mkdtemp(join(tmpdir(), "pa-"));
    const target = join(root, "data.txt");
    await writeFile(target, "before\n", "utf8");

    const cache = new PlanCache();
    const order: string[] = [];
    const snaps = {
      snapshot: vi.fn(async (tool: string, files: string[]) => {
        order.push("snapshot");
        expect(await readFile(target, "utf8")).toBe("before\n");
        return {
          snapshotId: "snap-apply",
          tool,
          ts: "now",
          files: files.map((source) => ({ source, backup: join(root, "backup") })),
        };
      }),
    } as unknown as SnapshotManager;

    const handler: PlanApplyHandler = {
      toolName: "test_apply_snapshot_timing",
      async buildPlan() {
        return {
          diff: "set after snapshot",
          affectedFiles: [target],
          targets: [{ path: target, kind: "text-file" }],
        };
      },
      async applyMutation(plan) {
        order.push(`apply:${plan.snapshotId}`);
        await writeFile(target, "after\n", "utf8");
        return {};
      },
    };

    const plan = await runPlanMode(handler, { mode: "plan" }, stubCtx, cache, snaps);
    expect(plan.ok).toBe(true);
    if (!plan.ok) throw new Error(plan.error.message);
    expect(plan.result.snapshot_id).toBeUndefined();
    expect(snaps.snapshot).not.toHaveBeenCalled();

    const apply = await runApplyMode(
      handler,
      { plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      stubCtx,
      cache,
      snaps,
    );

    expect(apply.ok).toBe(true);
    if (apply.ok) expect(apply.result.snapshot_id).toBe("snap-apply");
    expect(order).toEqual(["snapshot", "apply:snap-apply"]);
  });

  it("full plan → apply round-trip mutates the file", async () => {
    const root = await mkdtemp(join(tmpdir(), "pa-"));
    const target = join(root, "data.txt");
    await writeFile(target, "before\n", "utf8");

    const cache = new PlanCache();
    const snaps = new SnapshotManager(join(root, ".snap"), "sess-1");

    const handler: PlanApplyHandler = {
      toolName: "test_set_data",
      async buildPlan(args) {
        return {
          diff: `set: ${args.value}`,
          affectedFiles: [target],
          targets: [{ path: target, kind: "text-file" }],
        };
      },
      async applyMutation(plan) {
        await writeFile(target, `${plan.args.value}\n`, "utf8");
        return { path: target, written: true };
      },
    };

    const plan = await runPlanMode(
      handler,
      { mode: "plan", value: "hello" },
      stubCtx,
      cache,
      snaps,
    );
    expect(plan.ok).toBe(true);
    if (!plan.ok) throw new Error(plan.error.message);
    const planId = plan.result.planId;
    const leaseToken = plan.result.lease_token;

    const apply = await runApplyMode(
      handler,
      { plan_id: planId, lease_token: leaseToken },
      stubCtx,
      cache,
      snaps,
    );
    expect(apply.ok).toBe(true);

    expect(await readFile(target, "utf8")).toBe("hello\n");
  });

  it("apply fails with lease_violation when file mutated between plan and apply", async () => {
    const root = await mkdtemp(join(tmpdir(), "pa-"));
    const target = join(root, "data.txt");
    await writeFile(target, "original\n", "utf8");

    const cache = new PlanCache();
    const snaps = new SnapshotManager(join(root, ".snap"), "sess-1");

    const handler: PlanApplyHandler = {
      toolName: "test_mutate",
      async buildPlan() {
        return {
          diff: "x",
          affectedFiles: [target],
          targets: [{ path: target, kind: "text-file" }],
        };
      },
      async applyMutation() {
        return {};
      },
    };

    const plan = await runPlanMode(handler, { mode: "plan" }, stubCtx, cache, snaps);
    expect(plan.ok).toBe(true);
    if (!plan.ok) throw new Error(plan.error.message);

    // External mutation between plan and apply
    await writeFile(target, "EXTERNAL MUTATION\n", "utf8");

    const apply = await runApplyMode(
      handler,
      { plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      stubCtx,
      cache,
      snaps,
    );

    expect(apply.ok).toBe(false);
    if (!apply.ok) {
      expect(apply.error.code).toBe("lease_violation");
    }
  });

  it("apply fails with plan_expired_or_unknown for unknown plan", async () => {
    const cache = new PlanCache();
    const snaps = new SnapshotManager("/tmp/snap-test-unknown", "s");
    const handler: PlanApplyHandler = {
      toolName: "x",
      async buildPlan() {
        return { diff: "", affectedFiles: [], targets: [] };
      },
      async applyMutation() {
        return {};
      },
    };
    const apply = await runApplyMode(
      handler,
      { plan_id: "no-such-plan", lease_token: "t" },
      stubCtx,
      cache,
      snaps,
    );
    expect(apply.ok).toBe(false);
    if (!apply.ok) {
      expect(apply.error.code).toBe("plan_expired_or_unknown");
    }
  });

  it("apply fails with lease_token_mismatch when token differs", async () => {
    const root = await mkdtemp(join(tmpdir(), "pa-"));
    const target = join(root, "data.txt");
    await writeFile(target, "x", "utf8");

    const cache = new PlanCache();
    const snaps = new SnapshotManager(join(root, ".snap"), "s");
    const handler: PlanApplyHandler = {
      toolName: "x",
      async buildPlan() {
        return {
          diff: "",
          affectedFiles: [target],
          targets: [{ path: target, kind: "text-file" }],
        };
      },
      async applyMutation() {
        return {};
      },
    };
    const plan = await runPlanMode(handler, {}, stubCtx, cache, snaps);
    expect(plan.ok).toBe(true);
    if (!plan.ok) throw new Error(plan.error.message);
    const apply = await runApplyMode(
      handler,
      { plan_id: plan.result.planId, lease_token: "wrong-token" },
      stubCtx,
      cache,
      snaps,
    );
    expect(apply.ok).toBe(false);
    if (!apply.ok) {
      expect(apply.error.code).toBe("lease_token_mismatch");
    }
  });

  it("releases the target lock when applyMutation throws after snapshot", async () => {
    const root = await mkdtemp(join(tmpdir(), "pa-"));
    const target = join(root, "data.txt");
    await writeFile(target, "x", "utf8");
    const ctx = {
      ...stubCtx,
      config: {
        ...stubCtx.config,
        mo2Root: root,
        snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
        auditRoot: join(root, ".mo2-mcp", "audit"),
      },
      sessionId: "apply-failure-session",
    } satisfies ToolContext;
    const targets = [{ path: target, kind: "text-file" as const }];
    const cache = new PlanCache();
    const snaps = new SnapshotManager(join(root, ".snap"), "s");
    const handler: PlanApplyHandler = {
      toolName: "test_apply_failure_release",
      async buildPlan() {
        return {
          diff: "x",
          affectedFiles: [target],
          targets,
        };
      },
      async applyMutation() {
        throw new Error("mutation boom");
      },
    };
    const plan = await runPlanMode(handler, { mode: "plan" }, ctx, cache, snaps);
    expect(plan.ok).toBe(true);
    if (!plan.ok) throw new Error(plan.error.message);

    await expect(
      runApplyMode(
        handler,
        { plan_id: plan.result.planId, lease_token: plan.result.lease_token },
        ctx,
        cache,
        snaps,
      ),
    ).rejects.toThrow(/mutation boom/);

    const reacquire = await acquireLeasesForTargets(root, targets, {
      plan_id: "replacement-plan",
      mcp_pid: process.pid,
      mcp_session_id: "replacement-session",
      lease_token: "replacement-lease",
      tool_name: "test_apply_failure_release",
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
    });
    expect(reacquire.acquired).toBe(true);
    if (reacquire.acquired) await releaseLeaseLocks(root, reacquire.targetHashes, "replacement-plan");
  });

  it("plan fails with lease_held when another live process holds the target lock", async () => {
    const root = await mkdtemp(join(tmpdir(), "pa-"));
    const target = join(root, "data.txt");
    await writeFile(target, "x", "utf8");
    const ctx = {
      ...stubCtx,
      config: {
        ...stubCtx.config,
        mo2Root: root,
        snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
        auditRoot: join(root, ".mo2-mcp", "audit"),
      },
      sessionId: "blocked-session",
    } satisfies ToolContext;
    const targets = [{ path: target, kind: "text-file" as const }];
    const otherLock = await acquireLeasesForTargets(root, targets, {
      plan_id: "other-plan",
      mcp_pid: process.pid,
      mcp_session_id: "other-session",
      lease_token: "other-lease",
      tool_name: "test_locked_plan",
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
    });
    expect(otherLock.acquired).toBe(true);
    const cache = new PlanCache();
    const snaps = new SnapshotManager(join(root, ".snap"), "s");
    const handler: PlanApplyHandler = {
      toolName: "test_locked_plan",
      async buildPlan() {
        return {
          diff: "x",
          affectedFiles: [target],
          targets,
        };
      },
      async applyMutation() {
        return {};
      },
    };

    try {
      const plan = await runPlanMode(handler, { mode: "plan" }, ctx, cache, snaps);
      expect(plan.ok).toBe(false);
      if (!plan.ok) {
        expect(plan.error.code).toBe("lease_held");
        expect(plan.error.holder).toMatchObject({
          mcp_pid: process.pid,
          tool_name: "test_locked_plan",
        });
      }
      expect(cache.size()).toBe(0);
    } finally {
      if (otherLock.acquired) await releaseLeaseLocks(root, otherLock.targetHashes, "other-plan");
    }
  });
});

describe("routeToPlanApply (PLAN-PATCH P-B3)", () => {
  it("routes mode: plan to runPlanMode", async () => {
    const root = await mkdtemp(join(tmpdir(), "pa-"));
    const target = join(root, "data.txt");
    await writeFile(target, "x", "utf8");
    const cache = new PlanCache();
    const snaps = new SnapshotManager(join(root, ".snap"), "s");
    const handler: PlanApplyHandler = {
      toolName: "x",
      async buildPlan() {
        return {
          diff: "",
          affectedFiles: [target],
          targets: [{ path: target, kind: "text-file" }],
        };
      },
      async applyMutation() {
        return {};
      },
    };
    const result = await routeToPlanApply(handler, { mode: "plan" }, stubCtx, cache, snaps);
    expect(result.ok).toBe(true);
    if (result.ok && "result" in result) {
      expect("planId" in result.result).toBe(true);
    }
  });

  it("throws on invalid mode", async () => {
    const cache = new PlanCache();
    const snaps = new SnapshotManager("/tmp/sn", "s");
    const handler: PlanApplyHandler = {
      toolName: "x",
      async buildPlan() {
        return { diff: "", affectedFiles: [], targets: [] };
      },
      async applyMutation() {
        return {};
      },
    };
    await expect(
      routeToPlanApply(handler, { mode: "bogus" }, stubCtx, cache, snaps),
    ).rejects.toThrow(/invalid mode/);
  });
});
