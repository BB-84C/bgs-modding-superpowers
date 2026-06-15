/**
 * JSONL audit logger.
 *
 * Per oracle §8.1: MCP server is the single audit writer (sidecar returns
 * results; MCP logs them). Filename pattern <auditRoot>/<session>-<date>.jsonl
 * — session ID in filename prevents cross-session interleave.
 *
 * Never-throws contract: logging failures write to stderr and continue.
 * Tool calls must never abort because the audit log can't be written.
 */
import { appendFile, mkdir } from "node:fs/promises";
import { join } from "node:path";
import { createHash } from "node:crypto";
export class AuditLogger {
    auditRoot;
    sessionId;
    constructor(auditRoot, sessionId) {
        this.auditRoot = auditRoot;
        this.sessionId = sessionId;
    }
    filePath(date = new Date()) {
        const isoDate = date.toISOString().slice(0, 10);
        return join(this.auditRoot, `${this.sessionId}-${isoDate}.jsonl`);
    }
    async log(record) {
        try {
            await mkdir(this.auditRoot, { recursive: true });
            await appendFile(this.filePath(), `${JSON.stringify(record)}\n`, "utf8");
        }
        catch (e) {
            const message = e instanceof Error ? e.message : String(e);
            process.stderr.write(`[audit] log write failed: ${message}\n`);
        }
    }
}
/**
 * Hash args for audit log (first 16 hex chars of sha256).
 * Stable enough for grouping; not for security.
 */
export function hashArgs(args) {
    return createHash("sha256")
        .update(JSON.stringify(args ?? null))
        .digest("hex")
        .slice(0, 16);
}
