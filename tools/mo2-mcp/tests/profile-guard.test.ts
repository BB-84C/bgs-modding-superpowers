import { describe, it, expect } from "vitest";
import { assertActiveProfile } from "../src/profile-guard.js";
import type { ToolContext } from "../src/types.js";

function ctxWithActiveProfile(activeProfile?: string): ToolContext {
  // Legacy compat shape: ToolContext at runtime carries `binding`, but
  // requireBoundContext also accepts an old-shape ctx with `config` +
  // `pipeClient` for test fixtures that pre-date the lazy-bind refactor.
  // This fixture goes through that compat path.
  return {
    config: { mo2Root: "/test-mo2-root", allowedProfiles: ["Default"], permissionCeiling: "metadata-editable", deny: [], snapshotRoot: "/test-mo2-root/.mo2-mcp/snapshots", auditRoot: "/test-mo2-root/.mo2-mcp/audit" },
    pipeClient: activeProfile === undefined
      ? undefined
      : {
          call: async (method: string) => {
            expect(method).toBe("profile.active");
            return { ok: true, result: { name: activeProfile, path: `profiles/${activeProfile}` }, error: null };
          },
          close: () => {},
          discoverAndConnect: async () => {},
          isConnected: () => true,
        },
  } as unknown as ToolContext;
}

describe("assertActiveProfile", () => {
  it("is a no-op when there is no live pipe", async () => {
    await expect(assertActiveProfile(ctxWithActiveProfile(), "Alt")).resolves.toBeUndefined();
  });

  it("allows live mutation when requested profile matches active profile", async () => {
    await expect(assertActiveProfile(ctxWithActiveProfile("Default"), "Default")).resolves.toBeUndefined();
  });

  it("blocks live mutation when requested profile differs from active profile", async () => {
    await expect(assertActiveProfile(ctxWithActiveProfile("Default"), "BB84自用"))
      .rejects.toThrow(/cross_profile_live_mutation_blocked: requested='BB84自用', active='Default'/);
  });
});
