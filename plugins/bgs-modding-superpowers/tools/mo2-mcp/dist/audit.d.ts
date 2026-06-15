export type AuditDecision = "ok" | "refused" | "plan_generated" | "applied" | "lease_violation" | "rolled_back";
export interface AuditRecord {
    ts: string;
    sessionId: string;
    tool: string;
    mode?: "plan" | "apply";
    argsHash: string;
    decision: AuditDecision;
    ruleFindings?: unknown[];
    plan_id?: string;
    snapshotId?: string;
    durationMs: number;
    error?: {
        code: string;
        message: string;
    };
    details?: unknown;
}
export declare class AuditLogger {
    private auditRoot;
    private sessionId;
    constructor(auditRoot: string, sessionId: string);
    private filePath;
    log(record: AuditRecord): Promise<void>;
}
/**
 * Hash args for audit log (first 16 hex chars of sha256).
 * Stable enough for grouping; not for security.
 */
export declare function hashArgs(args: unknown): string;
