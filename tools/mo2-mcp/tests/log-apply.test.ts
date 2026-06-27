import { describe, expect, it } from "vitest";
import type { BoundContext } from "../src/binding.js";
import { logApplyEvent } from "../src/log-apply.js";

describe("logApplyEvent", () => {
  it("calls system.log_apply with the expected payload", async () => {
    const calls: Array<{ method: string; params: unknown }> = [];
    const ctx = {
      pipeClient: {
        call: async (method: string, params: unknown) => {
          calls.push({ method, params });
          return { ok: true, result: { logged: true }, error: null };
        },
      },
    } as unknown as BoundContext;

    await logApplyEvent("mo2_toggle_mod", "disabled \"Foo\"", ctx, "plan-1", "Default");

    expect(calls).toEqual([
      {
        method: "system.log_apply",
        params: {
          tool: "mo2_toggle_mod",
          plan_id: "plan-1",
          profile: "Default",
          summary: "disabled \"Foo\"",
        },
      },
    ]);
  });

  it("returns silently when offline", async () => {
    const ctx = {} as BoundContext;

    await expect(logApplyEvent("mo2_toggle_mod", "disabled \"Foo\"", ctx, "plan-1", "Default")).resolves.toBeUndefined();
  });

  it("does not propagate broker logging failures", async () => {
    const ctx = {
      pipeClient: {
        call: async () => {
          throw new Error("broker unavailable");
        },
      },
    } as unknown as BoundContext;

    await expect(logApplyEvent("mo2_toggle_mod", "disabled \"Foo\"", ctx, "plan-1", "Default")).resolves.toBeUndefined();
  });
});
