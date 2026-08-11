export function withPendingShutdownSave(dirtyState, pending) {
    return { ...dirtyState, pendingShutdownSave: pending };
}
/**
 * Fail-closed pending-save knowledge. Contract 0.23 dirty-state responses are
 * authoritative and replace this local fallback; older daemons retain the
 * locally observed lower bound until a session transition.
 */
export class PendingSaveTracker {
    pendingByKey = new Map();
    /**
     * A lower bound from daemon responses whose pending entries cannot all be
     * identified locally. Keep the maximum, not a running sum: the daemon count
     * describes the current save response, so repeatedly observing one queued
     * save must not invent more pending files.
     */
    reportedPendingCount = 0;
    observeSuccessfulSave(result) {
        if (!isRecord(result))
            return;
        const count = result.savePendingShutdownCount;
        const files = result.savedFilesPendingShutdown;
        if (typeof count !== "number" || !Number.isInteger(count) || count < 0) {
            this.observeDirtyState(result.dirtyState);
            return;
        }
        // This is the exact result shape emitted by xeAutomationSessionSave. A
        // zero count only says this invocation queued nothing; it does not prove a
        // prior queued rename has flushed, so existing pending state remains.
        for (const file of Array.isArray(files) ? files : []) {
            const key = fileKey(file);
            if (key)
                this.pendingByKey.set(key, file);
        }
        if (count > 0) {
            this.reportedPendingCount = Math.max(this.reportedPendingCount, count, this.pendingByKey.size);
        }
        // Contract 0.23 includes a post-save authoritative queue snapshot. Apply it
        // last so a confirmed zero can clear stale local fail-closed knowledge.
        this.observeDirtyState(result.dirtyState);
    }
    /** Returns true only when a complete authoritative 0.23 readback was applied. */
    observeDirtyState(value) {
        if (!isRecord(value))
            return false;
        const count = value.pendingShutdownCount;
        const files = value.pendingShutdownFiles;
        if (!Array.isArray(files) || typeof count !== "number" || !Number.isInteger(count) || count < 0) {
            return false;
        }
        this.pendingByKey.clear();
        for (let index = 0; index < files.length; index += 1) {
            const file = files[index];
            this.pendingByKey.set(fileKey(file) ?? `authoritative:${index}`, file);
        }
        this.reportedPendingCount = count;
        return true;
    }
    /** Applies only the validated post-drain queue from session.flush. */
    observePostFlushRemaining(files, count) {
        if (!Number.isInteger(count) || count < 0 || files.length !== count || files.some((file) => typeof file !== "string")) {
            throw new Error("Invalid post-flush pending state");
        }
        this.pendingByKey.clear();
        for (let index = 0; index < files.length; index += 1) {
            this.pendingByKey.set(`postFlush:${index}:${files[index]}`, files[index]);
        }
        this.reportedPendingCount = count;
    }
    snapshot() {
        return {
            count: Math.max(this.reportedPendingCount, this.pendingByKey.size),
            files: [...this.pendingByKey.values()],
        };
    }
    clearForSessionTransition() {
        this.pendingByKey.clear();
        this.reportedPendingCount = 0;
    }
}
/** Probe lifecycle authority without weakening the tracker on any failure. */
export async function refreshPendingSaveAuthority(adapter, tracker) {
    try {
        const env = await adapter.call({ command: "session.get_dirty_state", args: {} });
        if (!env.ok || !isRecord(env.result)) {
            return {
                ok: false,
                error: env.ok
                    ? new Error("Invalid dirty-state result: expected an object")
                    : env.error,
            };
        }
        tracker.observeDirtyState(env.result);
        return { ok: true, result: env.result };
    }
    catch (error) {
        return { ok: false, error };
    }
}
export function dirtyFileNames(value) {
    if (!Array.isArray(value))
        return [];
    const names = [];
    for (const entry of value) {
        if (typeof entry === "string" && entry.length > 0) {
            names.push(entry);
            continue;
        }
        if (!isRecord(entry))
            continue;
        const name = typeof entry.fileName === "string" && entry.fileName.length > 0
            ? entry.fileName
            : typeof entry.name === "string" && entry.name.length > 0
                ? entry.name
                : undefined;
        if (name)
            names.push(name);
    }
    return names;
}
export function pendingSaveLifecycleRisk(operation, pending, force) {
    if (pending.count === 0)
        return null;
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
        hint: "Pending-shutdown saves are not durable. Use xedit_flush with a contract-0.23 daemon; " +
            "force stop/restart hard-terminates managed xEdit and skips its pending-rename lifecycle. " +
            "temporary save files may remain available for manual recovery, but force:true explicitly abandons automated durability.",
        data: { pendingShutdownSave: pending },
    };
}
function isRecord(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
}
function fileKey(file) {
    if (typeof file === "string" && file.length > 0)
        return `string:${file}`;
    if (!isRecord(file))
        return null;
    if (typeof file.fileName === "string" && file.fileName.length > 0)
        return `fileName:${file.fileName}`;
    if (typeof file.name === "string" && file.name.length > 0)
        return `name:${file.name}`;
    return null;
}
//# sourceMappingURL=pending-save.js.map