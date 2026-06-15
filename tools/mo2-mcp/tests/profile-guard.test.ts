import { describe, it, expect } from "vitest";
import { assertActiveProfile } from "../src/profile-guard.js";
import type { ToolContext } from "../src/types.js";

function ctxWithActiveProfile(activeProfile?: string): ToolContext {
  return {
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
        } as unknown as ToolContext["pipeClient"],
  } as ToolContext;
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
