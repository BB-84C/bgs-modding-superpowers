import type { LeaseTarget } from "./lease.js";
export declare const LEASE_LOCK_TTL_MS: number;
export interface LeaseLockMetadata {
    plan_id: string;
    mcp_pid: number;
    mcp_session_id: string;
    lease_token: string;
    tool_name: string;
    created_at: string;
    expires_at: string;
}
export interface LeaseLockHolder {
    mcp_pid: number;
    created_at: string;
    tool_name: string;
}
export type LeaseLockAcquireResult = {
    acquired: true;
    lockPath: string;
} | {
    acquired: false;
    lockPath: string;
    holder: LeaseLockHolder;
};
export type LeaseLocksAcquireResult = {
    acquired: true;
    lockPaths: string[];
    targetHashes: string[];
} | {
    acquired: false;
    holders: LeaseLockHolder[];
    acquiredLocks: string[];
    targetHashes: string[];
};
export interface LeaseLockAcquireOptions {
    isPidAlive?: (pid: number) => Promise<boolean>;
}
export declare function computeLeaseTargetHash(targets: LeaseTarget[]): string;
export declare function computeLeaseTargetPathHash(path: string): string;
export declare function computeLeaseTargetHashes(targets: LeaseTarget[]): string[];
export declare function leaseLockPath(mo2Root: string, targetHash: string): string;
export declare function isPidAlive(pid: number): Promise<boolean>;
export declare function acquireLeaseLock(mo2Root: string, targetHash: string, metadata: LeaseLockMetadata, options?: LeaseLockAcquireOptions): Promise<LeaseLockAcquireResult>;
export declare function acquireLeasesForTargets(mo2Root: string, targets: LeaseTarget[], metadata: LeaseLockMetadata, options?: LeaseLockAcquireOptions): Promise<LeaseLocksAcquireResult>;
export declare function releaseLeaseLock(mo2Root: string, targetHash: string, planId: string): Promise<void>;
export declare function releaseLeaseLocks(mo2Root: string, targetHashes: string[], planId: string): Promise<void>;
