import { describe, it, expect, beforeEach } from "vitest";
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
      ttlMs: -1, // already expired
    });
    expect(c.get(rec.planId)).toBeNull();
  });
});

describe("runPlanMode + runApplyMode", () => {
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
    const planId = plan.result.planId;
    const leaseToken = plan.result.lease_token;

    const apply = await runApplyMode(
      handler,
      { plan_id: planId, lease_token: leaseToken },
      stubCtx,
      cache,
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

    // External mutation between plan and apply
    await writeFile(target, "EXTERNAL MUTATION\n", "utf8");

    const apply = await runApplyMode(
      handler,
      { plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      stubCtx,
      cache,
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
    const apply = await runApplyMode(
      handler,
      { plan_id: plan.result.planId, lease_token: "wrong-token" },
      stubCtx,
      cache,
    );
    expect(apply.ok).toBe(false);
    if (!apply.ok) {
      expect(apply.error.code).toBe("lease_token_mismatch");
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
