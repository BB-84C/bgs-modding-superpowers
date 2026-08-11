import { MCP_ERROR_CODES } from "./types.js";
export function lifecycleNotReadyHint(status, hasManagedDaemon, lastFlush) {
    if (status === "failed" && hasManagedDaemon && lastFlush?.daemonExited === false) {
        return "Managed xEdit may still be closing and completing its final rename. " +
            "Retry xedit_health shortly to confirm exit; do not force termination while closing may still complete.";
    }
    if (status === "not_started")
        return "Daemon not started. Call xedit_start.";
    if (status === "starting")
        return "Daemon still starting. Poll xedit_status.";
    if (status === "failed")
        return "Daemon failed to start; inspect data.error.";
    return "Daemon is ready.";
}
export function launchKickoffDecision(status, hasManagedDaemon) {
    if (status === "starting")
        return { allowed: false, reason: "already_starting" };
    if (status === "ready")
        return { allowed: false, reason: "already_ready" };
    if (status === "failed" && hasManagedDaemon) {
        return { allowed: false, reason: "retained_managed_process" };
    }
    return { allowed: true };
}
export function dirtyProbeLifecycleDecision(operation, probeAvailable, force) {
    if (probeAvailable)
        return { allowed: true, operation };
    if (force)
        return { allowed: true, operation, risk: "dirty_state_probe_unavailable" };
    return { allowed: false, operation, code: MCP_ERROR_CODES.DIRTY_STATE_UNAVAILABLE };
}
//# sourceMappingURL=lifecycle-decisions.js.map