/**
 * Plan/apply pipeline — one tool with `mode: "plan" | "apply"` arg.
 *
 * Plan mode: compute lease, store record, return
 *   { plan_id, lease_token, diff, affected_files, expires_at }.
 * Apply mode: consume plan_id + lease_token, re-verify lease, snapshot the
 *   current pre-apply state, then run handler.
 *
 * PLAN-PATCH P-B3: every S4/S5 tool calls routeToPlanApply(handler, args, ctx).
 */
import { randomUUID } from "node:crypto";
import {
  computeLease,
  verifyLease,
  type Lease,
  type LeaseTarget,
} from "./lease.js";
import type { SnapshotManager } from "./snapshot.js";
import type { ToolContext } from "./types.js";
import { requireBoundContext, bindingSnapshot } from "./binding.js";
import {
  acquireLeasesForTargets,
  LEASE_LOCK_TTL_MS,
  releaseLeaseLocks,
} from "./lease-lock.js";

export interface PlanRecord {
  planId: string;
  tool: string;
  args: Record<string, unknown>;
  diff: string;
  affectedFiles: string[];
  lease: Lease;
  leaseLockTargetHashes: string[];
  snapshotId?: string;
  /** ms epoch */
  expiresAt: number;
}

/**
 * In-memory cache of pending plans. Expires after `defaultTtlMs` (10 min).
 */
export class PlanCache {
  private plans = new Map<string, PlanRecord>();
  private defaultTtlMs = LEASE_LOCK_TTL_MS;

  store(
    plan: Omit<PlanRecord, "planId" | "expiresAt"> & {
      ttlMs?: number;
      planId?: string;
      expiresAt?: number;
    },
  ): PlanRecord {
    const planId = plan.planId ?? randomUUID();
    const expiresAt = plan.expiresAt ?? Date.now() + (plan.ttlMs ?? this.defaultTtlMs);
    const { ttlMs: _ignored, planId: _planId, expiresAt: _expiresAt, ...rest } = plan;
    const rec: PlanRecord = { ...rest, planId, expiresAt };
    this.plans.set(planId, rec);
    return rec;
  }

  get(planId: string): PlanRecord | null {
    const rec = this.plans.get(planId);
    if (!rec) return null;
    if (Date.now() > rec.expiresAt) {
      this.plans.delete(planId);
      return null;
    }
    return rec;
  }

  consume(planId: string): PlanRecord | null {
    const rec = this.get(planId);
    if (rec) this.plans.delete(planId);
    return rec;
  }

  purgeExpired(): void {
    const now = Date.now();
    for (const [id, rec] of this.plans) {
      if (now > rec.expiresAt) this.plans.delete(id);
    }
  }

  size(): number {
    return this.plans.size;
  }
}

/**
 * Handler that an individual T2/T3 tool implements.
 * - buildPlan: compute diff + affected files + lease targets
 * - applyMutation: execute the mutation given the validated plan
 */
export interface PlanApplyHandler {
  toolName: string;
  buildPlan(
    args: Record<string, unknown>,
    ctx: ToolContext,
  ): Promise<{
    diff: string;
    affectedFiles: string[];
    targets: LeaseTarget[];
  }>;
  applyMutation(
    plan: PlanRecord,
    ctx: ToolContext,
  ): Promise<Record<string, unknown>>;
}

export interface PlanModeOk {
  ok: true;
  result: {
    mode: "plan";
    plan_id: string;
    planId: string;
    lease_token: string;
    diff: string;
    affected_files: string[];
    expires_at: string;
    snapshot_id?: string;
  };
}

export interface PlanModeError {
  ok: false;
  error: {
    code: "lease_held";
    message: string;
    holder: {
      tool: string;
      tool_name: string;
      mcp_pid: number;
      created_at: string;
    };
    holders: Array<{
      tool: string;
      tool_name: string;
      mcp_pid: number;
      created_at: string;
    }>;
  };
}

export type PlanModeResult = PlanModeOk | PlanModeError;

async function releasePlanLockBestEffort(
  ctx: ToolContext,
  rec: PlanRecord,
): Promise<void> {
  try {
    await releaseLeaseLocks(requireBoundContext(ctx).config.mo2Root, rec.leaseLockTargetHashes, rec.planId);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`[lease-lock] failed to release ${rec.planId}: ${message}\n`);
  }
}

export async function runPlanMode(
  handler: PlanApplyHandler,
  args: Record<string, unknown>,
  ctx: ToolContext,
  cache: PlanCache,
  _snapshots: SnapshotManager,
): Promise<PlanModeResult> {
  const built = await handler.buildPlan(args, ctx);
  const lease = await computeLease(built.targets);
  const planId = randomUUID();
  const expiresAt = Date.now() + LEASE_LOCK_TTL_MS;
  const createdAt = new Date().toISOString();
  const lock = await acquireLeasesForTargets(requireBoundContext(ctx).config.mo2Root, built.targets, {
    plan_id: planId,
    mcp_pid: process.pid,
    mcp_session_id: ctx.sessionId,
    lease_token: lease.token,
    tool_name: handler.toolName,
    created_at: createdAt,
    expires_at: new Date(expiresAt).toISOString(),
  });
  if (!lock.acquired) {
    const holders = lock.holders.map((holder) => ({
      tool: holder.tool_name,
      tool_name: holder.tool_name,
      mcp_pid: holder.mcp_pid,
      created_at: holder.created_at,
    }));
    const firstHolder = holders[0];
    return {
      ok: false,
      error: {
        code: "lease_held",
        message: `Target is already locked by ${firstHolder.tool_name} in MCP process ${firstHolder.mcp_pid}`,
        holder: firstHolder,
        holders,
      },
    };
  }
  let rec: PlanRecord;
  try {
    rec = cache.store({
      planId,
      expiresAt,
      tool: handler.toolName,
      args,
      diff: built.diff,
      affectedFiles: built.affectedFiles,
      lease,
      leaseLockTargetHashes: lock.targetHashes,
    });
  } catch (error) {
    await releaseLeaseLocks(requireBoundContext(ctx).config.mo2Root, lock.targetHashes, planId);
    throw error;
  }
  return {
    ok: true,
    result: {
      mode: "plan",
      plan_id: rec.planId,
      planId: rec.planId,
      lease_token: lease.token,
      diff: built.diff,
      affected_files: built.affectedFiles,
      expires_at: new Date(rec.expiresAt).toISOString(),
    },
  };
}

export type ApplyResult =
  | {
      ok: true;
      result: Record<string, unknown> & { mode: "apply"; plan_id: string; snapshot_id?: string };
    }
  | {
      ok: false;
      error: { code: string; message: string; drift?: unknown };
    };

export async function runApplyMode(
  handler: PlanApplyHandler,
  args: { plan_id: string; lease_token: string },
  ctx: ToolContext,
  cache: PlanCache,
  snapshots: SnapshotManager,
): Promise<ApplyResult> {
  const rec = cache.consume(args.plan_id);
  if (!rec) {
    return {
      ok: false,
      error: {
        code: "plan_expired_or_unknown",
        message: `plan ${args.plan_id} not found or expired`,
      },
    };
  }
  if (rec.lease.token !== args.lease_token) {
    await releasePlanLockBestEffort(ctx, rec);
    return {
      ok: false,
      error: {
        code: "lease_token_mismatch",
        message: "stored plan lease differs from supplied",
      },
    };
  }
  const v = await verifyLease(rec.lease);
  if (!v.valid) {
    await releasePlanLockBestEffort(ctx, rec);
    return {
      ok: false,
      error: {
        code: "lease_violation",
        message: "Profile state changed since plan was generated",
        drift: v.drift,
      },
    };
  }

  try {
    const snapshot = await snapshots.snapshot(handler.toolName, rec.affectedFiles);
    rec.snapshotId = snapshot.snapshotId;
    const result = await handler.applyMutation(rec, ctx);
    return {
      ok: true,
      result: {
        mode: "apply",
        plan_id: rec.planId,
        snapshot_id: rec.snapshotId,
        ...result,
      },
    };
  } finally {
    await releasePlanLockBestEffort(ctx, rec);
  }
}

/**
 * PLAN-PATCH P-B3: branch on mode arg. Used by every S4/S5 plan/apply tool.
 *
 * Requires ToolContext to carry `plans` and `snapshots`. S2.14 bootstrap
 * extends ToolContext for that wiring; if your ToolContext doesn't yet
 * carry them, pass them as additional args.
 */
export async function routeToPlanApply(
  handler: PlanApplyHandler,
  args: Record<string, unknown>,
  ctx: ToolContext,
  cache: PlanCache,
  snapshots: SnapshotManager,
): Promise<PlanModeResult | ApplyResult> {
  const mode = args.mode;
  if (mode === "plan") {
    return runPlanMode(handler, args, ctx, cache, snapshots);
  }
  if (mode === "apply") {
    return runApplyMode(
      handler,
      args as unknown as { plan_id: string; lease_token: string },
      ctx,
      cache,
      snapshots,
    );
  }
  throw new Error(`invalid mode: ${String(mode)} (must be "plan" or "apply")`);
}
