import { describe, expect, it } from "vitest";

import {
  dirtyProbeLifecycleDecision,
  launchKickoffDecision,
  lifecycleNotReadyHint,
} from "../../src/lifecycle-decisions.js";

describe("lifecycle fail-closed decisions", () => {
  it("blocks a fresh start when failed state retains a managed daemon", () => {
    expect(launchKickoffDecision("failed", true)).toEqual({
      allowed: false,
      reason: "retained_managed_process",
    });
    expect(launchKickoffDecision("failed", false)).toEqual({ allowed: true });
  });

  it.each(["stop", "restart"] as const)("refuses %s when ready dirty-state probe failed", (operation) => {
    expect(dirtyProbeLifecycleDecision(operation, false, false)).toMatchObject({
      allowed: false,
      code: "dirty_state_unavailable",
      operation,
    });
  });

  it.each(["stop", "restart"] as const)("allows forced %s with explicit probe-unavailable risk", (operation) => {
    expect(dirtyProbeLifecycleDecision(operation, false, true)).toEqual({
      allowed: true,
      risk: "dirty_state_probe_unavailable",
      operation,
    });
    expect(dirtyProbeLifecycleDecision(operation, true, false)).toEqual({ allowed: true, operation });
  });

  it("describes failed retained flush as closing and routes to xedit_health", () => {
    const hint = lifecycleNotReadyHint("failed", true, { daemonExited: false });
    expect(hint).toContain("closing");
    expect(hint).toContain("final rename");
    expect(hint).toContain("xedit_health");
    expect(hint).not.toContain("failed to start");
    expect(hint).toContain("do not force");
  });

  it("preserves ordinary failed-to-start guidance without retained flush state", () => {
    expect(lifecycleNotReadyHint("failed", false)).toContain("failed to start");
  });
});
