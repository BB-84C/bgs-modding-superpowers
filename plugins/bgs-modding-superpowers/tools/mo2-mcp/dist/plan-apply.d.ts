import { type Lease, type LeaseTarget } from "./lease.js";
import type { SnapshotManager } from "./snapshot.js";
import type { ToolContext } from "./types.js";
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
export declare class PlanCache {
    private plans;
    private defaultTtlMs;
    store(plan: Omit<PlanRecord, "planId" | "expiresAt"> & {
        ttlMs?: number;
        planId?: string;
        expiresAt?: number;
    }): PlanRecord;
    get(planId: string): PlanRecord | null;
    consume(planId: string): PlanRecord | null;
    purgeExpired(): void;
    size(): number;
}
/**
 * Handler that an individual T2/T3 tool implements.
 * - buildPlan: compute diff + affected files + lease targets
 * - applyMutation: execute the mutation given the validated plan
 * - acquirePlanLock?: opt out of plan-time filesystem lease locking
 *   (default true). When false, runPlanMode records the lease fingerprint
 *   without acquiring a filesystem lock; runApplyMode acquires the lock
 *   briefly at apply time, verifies the fingerprint, mutates, releases.
 *   Use for tools whose plan phase is pure read and whose lease targets
 *   are shared write surfaces (multiple plans for distinct mods that all
 *   land in the same profile's modlist.txt / plugins.txt). BUG-14 BUG-F
 *   (issue #14): mo2_install opts in so parallel plans for distinct
 *   mod_names don't block each other.
 */
export interface PlanApplyHandler {
    toolName: string;
    acquirePlanLock?: boolean;
    buildPlan(args: Record<string, unknown>, ctx: ToolContext): Promise<{
        diff: string;
        affectedFiles: string[];
        targets: LeaseTarget[];
    }>;
    applyMutation(plan: PlanRecord, ctx: ToolContext): Promise<Record<string, unknown>>;
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
export declare function runPlanMode(handler: PlanApplyHandler, args: Record<string, unknown>, ctx: ToolContext, cache: PlanCache, _snapshots: SnapshotManager): Promise<PlanModeResult>;
export type ApplyResult = {
    ok: true;
    result: Record<string, unknown> & {
        mode: "apply";
        plan_id: string;
        snapshot_id?: string;
    };
} | {
    ok: false;
    error: {
        code: string;
        message: string;
        drift?: unknown;
    };
};
export declare function runApplyMode(handler: PlanApplyHandler, args: {
    plan_id: string;
    lease_token: string;
}, ctx: ToolContext, cache: PlanCache, snapshots: SnapshotManager): Promise<ApplyResult>;
/**
 * PLAN-PATCH P-B3: branch on mode arg. Used by every S4/S5 plan/apply tool.
 *
 * Requires ToolContext to carry `plans` and `snapshots`. S2.14 bootstrap
 * extends ToolContext for that wiring; if your ToolContext doesn't yet
 * carry them, pass them as additional args.
 */
export declare function routeToPlanApply(handler: PlanApplyHandler, args: Record<string, unknown>, ctx: ToolContext, cache: PlanCache, snapshots: SnapshotManager): Promise<PlanModeResult | ApplyResult>;
