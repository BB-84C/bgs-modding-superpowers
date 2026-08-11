import { MCP_ERROR_CODES } from "./types.js";

export type PublicLaunchStatus = "not_started" | "starting" | "ready" | "failed";
export type LifecycleOperation = "stop" | "restart";

export function lifecycleNotReadyHint(
  status: PublicLaunchStatus,
  hasManagedDaemon: boolean,
  lastFlush?: { daemonExited?: boolean },
): string {
  if (status === "failed" && hasManagedDaemon && lastFlush?.daemonExited === false) {
    return "Managed xEdit may still be closing and completing its final rename. " +
      "Retry xedit_health shortly to confirm exit; do not force termination while closing may still complete.";
  }
  if (status === "not_started") return "Daemon not started. Call xedit_start.";
  if (status === "starting") return "Daemon still starting. Poll xedit_status.";
  if (status === "failed") return "Daemon failed to start; inspect data.error.";
  return "Daemon is ready.";
}

export function launchKickoffDecision(
  status: PublicLaunchStatus,
  hasManagedDaemon: boolean,
): { allowed: true } | { allowed: false; reason: "already_starting" | "already_ready" | "retained_managed_process" } {
  if (status === "starting") return { allowed: false, reason: "already_starting" };
  if (status === "ready") return { allowed: false, reason: "already_ready" };
  if (status === "failed" && hasManagedDaemon) {
    return { allowed: false, reason: "retained_managed_process" };
  }
  return { allowed: true };
}

export function dirtyProbeLifecycleDecision(
  operation: LifecycleOperation,
  probeAvailable: boolean,
  force: boolean,
):
  | { allowed: true; operation: LifecycleOperation; risk?: "dirty_state_probe_unavailable" }
  | { allowed: false; operation: LifecycleOperation; code: typeof MCP_ERROR_CODES.DIRTY_STATE_UNAVAILABLE } {
  if (probeAvailable) return { allowed: true, operation };
  if (force) return { allowed: true, operation, risk: "dirty_state_probe_unavailable" };
  return { allowed: false, operation, code: MCP_ERROR_CODES.DIRTY_STATE_UNAVAILABLE };
}
