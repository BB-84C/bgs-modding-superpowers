export interface PendingShutdownSave {
  count: number;
  files: unknown[];
}

export type LifecycleOperation = "stop" | "restart";

export interface PendingSaveRefusal {
  code: "pending_save";
  severity: "CRITICAL";
  summary: string;
  hint: string;
  data: { pendingShutdownSave: PendingShutdownSave };
}

export interface PendingSaveAbandonment {
  abandonment: true;
  risk: "pending_shutdown_save_may_be_lost";
  pendingShutdownSave: PendingShutdownSave;
}

export function withPendingShutdownSave<T extends Record<string, unknown>>(
  dirtyState: T,
  pending: PendingShutdownSave,
): T & { pendingShutdownSave: PendingShutdownSave } {
  return { ...dirtyState, pendingShutdownSave: pending };
}

/**
 * Local fail-closed knowledge of saves xEdit has acknowledged as queued for
 * shutdown. xEdit's dirty state becomes false after such a save, so it cannot
 * be used to clear this guard. The daemon has no queue-inspection/flush verb;
 * pending entries therefore persist until this MCP session itself transitions.
 */
export class PendingSaveTracker {
  private readonly pendingByKey = new Map<string, unknown>();
  /**
   * A lower bound from daemon responses whose pending entries cannot all be
   * identified locally. Keep the maximum, not a running sum: the daemon count
   * describes the current save response, so repeatedly observing one queued
   * save must not invent more pending files.
   */
  private reportedPendingCount = 0;

  observeSuccessfulSave(result: unknown): void {
    if (!isRecord(result)) return;

    const count = result.savePendingShutdownCount;
    const files = result.savedFilesPendingShutdown;
    if (typeof count !== "number" || !Number.isInteger(count) || count < 0) {
      return;
    }

    // This is the exact result shape emitted by xeAutomationSessionSave. A
    // zero count only says this invocation queued nothing; it does not prove a
    // prior queued rename has flushed, so existing pending state remains.
    for (const file of Array.isArray(files) ? files : []) {
      const key = fileKey(file);
      if (key) this.pendingByKey.set(key, file);
    }
    if (count > 0) {
      this.reportedPendingCount = Math.max(this.reportedPendingCount, count, this.pendingByKey.size);
    }
  }

  snapshot(): PendingShutdownSave {
    return {
      count: Math.max(this.reportedPendingCount, this.pendingByKey.size),
      files: [...this.pendingByKey.values()],
    };
  }

  clearForSessionTransition(): void {
    this.pendingByKey.clear();
    this.reportedPendingCount = 0;
  }
}

export function pendingSaveLifecycleRisk(
  operation: LifecycleOperation,
  pending: PendingShutdownSave,
  force: boolean,
): PendingSaveRefusal | PendingSaveAbandonment | null {
  if (pending.count === 0) return null;

  if (force) {
    return {
      abandonment: true,
      risk: "pending_shutdown_save_may_be_lost",
      pendingShutdownSave: pending,
    };
  }

  return {
    code: "pending_save",
    severity: "CRITICAL",
    summary: `xEdit has ${pending.count} save(s) pending shutdown. Refusing to ${operation}.`,
    hint:
      "Pending-shutdown saves are not durable and xEdit exposes no queue flush/readback command. " +
      "Do not stop or restart this daemon; force:true explicitly abandons the pending save state.",
    data: { pendingShutdownSave: pending },
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function fileKey(file: unknown): string | null {
  if (typeof file === "string" && file.length > 0) return `string:${file}`;
  if (!isRecord(file)) return null;
  if (typeof file.fileName === "string" && file.fileName.length > 0) return `fileName:${file.fileName}`;
  if (typeof file.name === "string" && file.name.length > 0) return `name:${file.name}`;
  return null;
}
