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
import { computeLease, verifyLease, } from "./lease.js";
import { acquireLeasesForTargets, LEASE_LOCK_TTL_MS, releaseLeaseLocks, } from "./lease-lock.js";
/**
 * In-memory cache of pending plans. Expires after `defaultTtlMs` (10 min).
 */
export class PlanCache {
    plans = new Map();
    defaultTtlMs = LEASE_LOCK_TTL_MS;
    store(plan) {
        const planId = plan.planId ?? randomUUID();
        const expiresAt = plan.expiresAt ?? Date.now() + (plan.ttlMs ?? this.defaultTtlMs);
        const { ttlMs: _ignored, planId: _planId, expiresAt: _expiresAt, ...rest } = plan;
        const rec = { ...rest, planId, expiresAt };
        this.plans.set(planId, rec);
        return rec;
    }
    get(planId) {
        const rec = this.plans.get(planId);
        if (!rec)
            return null;
        if (Date.now() > rec.expiresAt) {
            this.plans.delete(planId);
            return null;
        }
        return rec;
    }
    consume(planId) {
        const rec = this.get(planId);
        if (rec)
            this.plans.delete(planId);
        return rec;
    }
    purgeExpired() {
        const now = Date.now();
        for (const [id, rec] of this.plans) {
            if (now > rec.expiresAt)
                this.plans.delete(id);
        }
    }
    size() {
        return this.plans.size;
    }
}
async function releasePlanLockBestEffort(ctx, rec) {
    try {
        await releaseLeaseLocks(ctx.config.mo2Root, rec.leaseLockTargetHashes, rec.planId);
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        process.stderr.write(`[lease-lock] failed to release ${rec.planId}: ${message}\n`);
    }
}
export async function runPlanMode(handler, args, ctx, cache, _snapshots) {
    const built = await handler.buildPlan(args, ctx);
    const lease = await computeLease(built.targets);
    const planId = randomUUID();
    const expiresAt = Date.now() + LEASE_LOCK_TTL_MS;
    const createdAt = new Date().toISOString();
    const lock = await acquireLeasesForTargets(ctx.config.mo2Root, built.targets, {
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
    let rec;
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
    }
    catch (error) {
        await releaseLeaseLocks(ctx.config.mo2Root, lock.targetHashes, planId);
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
export async function runApplyMode(handler, args, ctx, cache, snapshots) {
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
    }
    finally {
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
export async function routeToPlanApply(handler, args, ctx, cache, snapshots) {
    const mode = args.mode;
    if (mode === "plan") {
        return runPlanMode(handler, args, ctx, cache, snapshots);
    }
    if (mode === "apply") {
        return runApplyMode(handler, args, ctx, cache, snapshots);
    }
    throw new Error(`invalid mode: ${String(mode)} (must be "plan" or "apply")`);
}
