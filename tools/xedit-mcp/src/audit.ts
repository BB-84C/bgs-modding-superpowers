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
}

export interface AuditLogger {
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
      const ts = now();
      const day = ts.toISOString().slice(0, 10);
      const line = JSON.stringify({ ts: ts.toISOString(), ...record }) + "\n";
      const filePath = join(opts.baseDir, `${day}.jsonl`);
      try {
        await mkdir(opts.baseDir, { recursive: true });
        await appendFile(filePath, line, "utf8");
      } catch (err) {
        onError(err);
      }
    },
  };
}
