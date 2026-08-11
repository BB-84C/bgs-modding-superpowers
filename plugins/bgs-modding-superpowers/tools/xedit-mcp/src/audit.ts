import { mkdir, appendFile } from "node:fs/promises";
import { join } from "node:path";

export interface AuditRecord {
  tool: string;
  argsHash: string;
  decision: "ok" | "refused" | "warned";
  ok: boolean;
  code?: string;
  ruleHits?: string[];
  snapshotId?: string;
  daemonPid?: number;
  sessionId?: string;
  /** Explicit lifecycle abandonment reason, when one was authorized. */
  risk?: string;
  /** Pending-save snapshot at lifecycle or flush decision boundaries. */
  pendingShutdownSave?: { count: number; files: unknown[] };
  force?: boolean;
  flushed?: { attempted: number; renamed: number; failed: number };
  pendingRemaining?: number;
  daemonExited?: boolean;
  flushOutcome?: "known" | "unknown";
  dirtyStateProbeUnavailable?: boolean;
}

export interface AuditLogger {
  /**
   * Append one audit record. Best-effort, append-only.
   *
   * Contract:
   * - Never throws. Errors (mkdir/serialize/append failures) are routed to `onError` (default: silently swallowed).
   * - Order is not guaranteed under concurrent calls; relative line order may interleave.
   * - No fsync. Crash-durability is not provided. Suitable for forensic audit trail under normal shutdown, not for hot-path durability guarantees.
   * - Production callers SHOULD provide `onError` to avoid silent loss of audit records.
   */
  append(record: AuditRecord): Promise<void>;
}

export interface AuditLoggerOptions {
  baseDir: string;
  onError?: (err: unknown) => void;
  /** Override clock for tests. */
  now?: () => Date;
}

export function createAuditLogger(opts: AuditLoggerOptions): AuditLogger {
  const now = opts.now ?? (() => new Date());
  const onError = opts.onError ?? (() => {});

  return {
    async append(record: AuditRecord) {
      try {
        const ts = now();
        const day = ts.toISOString().slice(0, 10);
        const line = JSON.stringify({ ...record, ts: ts.toISOString() }) + "\n";
        const filePath = join(opts.baseDir, `${day}.jsonl`);
        await mkdir(opts.baseDir, { recursive: true });
        await appendFile(filePath, line, "utf8");
      } catch (err) {
        try {
          onError(err);
        } catch {
          /* swallow callback's own throws to honour the never-throws contract */
        }
      }
    },
  };
}
