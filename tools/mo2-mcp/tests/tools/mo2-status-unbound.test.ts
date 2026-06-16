import { describe, expect, it, beforeEach } from "vitest";
import { join } from "node:path";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { _clearToolsForTests, getTool } from "../../src/tool-registry.js";
import { BindingManager } from "../../src/binding.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function makeUnboundCtx(): Promise<ToolContext> {
  const root = await mkdtemp(join(tmpdir(), "mo2-status-unbound-"));
  return {
    binding: new BindingManager({ log: () => {} }),
    sessionId: "unbound-status",
    plans: new PlanCache(),
    snapshots: new SnapshotManager(join(root, "snapshots"), "unbound-status"),
    audit: new AuditLogger(join(root, "audit"), "unbound-status"),
  };
}

describe("mo2_status unbound", () => {
  beforeEach(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-status.js");
  });

  it("returns a sensible unbound view instead of throwing", async () => {
    const ctx = await makeUnboundCtx();
    const tool = getTool("mo2_status")!;

    const result = await tool.handler({}, ctx);

    expect(result).toEqual({
      ok: true,
      bound: false,
      snapshot: { state: "unbound" },
      hint: "call mo2_session({ mo2Root }) to bind",
    });
  });
});
