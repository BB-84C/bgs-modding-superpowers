import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _fixture(): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-sm-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(
    join(root, "profiles", "Default", "modlist.txt"),
    "+TopMod\n+MiddleMod\n+MySection_separator\n+BottomMod\n",
    "utf8",
  );
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
  await mkdir(join(root, "profiles", "BB84自用"), { recursive: true });
  await writeFile(join(root, "profiles", "BB84自用", "modlist.txt"), "+BottomMod\n+TopMod\n", "utf8");
  await writeFile(join(root, "profiles", "BB84自用", "plugins.txt"), "", "utf8");
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\n[Settings]\nbase_directory=" + root + "\n",
    "utf8",
  );
  const ctx: ToolContext = {
    config: {
      mo2Root: root,
      permissionCeiling: "full-control",
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
      auditRoot: join(root, ".mo2-mcp", "audit"),
    },
    sessionId: "test",
    plans: new PlanCache(),
    snapshots: new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "test"),
    audit: new AuditLogger(join(root, ".mo2-mcp", "audit"), "test"),
  };
  return { root, ctx };
}

describe("mo2_send_mod_to", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-send-mod-to.js");
  });

  it("registers as T3", () => {
    expect(getTool("mo2_send_mod_to")?.tier).toBe("T3");
  });

  it("plan with target_mode=top returns highest priority", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_send_mod_to")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "BottomMod", target_mode: "top" },
      ctx,
    )) as { ok: boolean; result: { diff: string } };
    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("BottomMod");
  });

  it("plan with target_mode=above_separator finds the separator", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_send_mod_to")!;
    const plan = (await tool.handler(
      {
        mode: "plan",
        name: "BottomMod",
        target_mode: "above_separator",
        target_separator: "MySection_separator",
      },
      ctx,
    )) as { ok: boolean };
    expect(plan.ok).toBe(true);
  });

  // BUG-14 BUG-B regression (issue #14): with separators occupying upper-priority
  // slots, `sep.priority + 1` (full-priority space) overshot the broker validator
  // `max_priority = len(non_separator_mods)` (non-separator space). Verify the
  // plan-side computed priority now lives in non-separator space and would pass
  // the broker validator for BB84's real-world layout.
  describe("BUG-14 BUG-B: above_separator priority lives in non-separator space", () => {
    async function _fixtureWithSeparatorsOnTop(): Promise<{
      root: string;
      ctx: ToolContext;
      brokerCalls: Array<{ method: string; payload: unknown }>;
    }> {
      const root = await mkdtemp(join(tmpdir(), "mo2-bug-b-"));
      await mkdir(join(root, "profiles", "Default"), { recursive: true });
      // 10 lines, 5 separators in upper slots (mimics BB84's distribution
      // where separators occupy the top of modlist.txt). modCount=10:
      //   idx=0 Sep1                 -> priority=9 (separator)
      //   idx=1 Sep2                 -> priority=8 (separator)
      //   idx=2 Sep3                 -> priority=7 (separator)
      //   idx=3 TargetSep_separator  -> priority=6 (separator) <- target
      //   idx=4 Sep5                 -> priority=5 (separator)
      //   idx=5 Mod1                 -> priority=4
      //   idx=6 Mod2                 -> priority=3
      //   idx=7 Mod3                 -> priority=2
      //   idx=8 Mod4                 -> priority=1
      //   idx=9 BottomMod            -> priority=0
      // nonSep.length=5, broker max_priority=5.
      // OLD: sep.priority + 1 = 7 -> broker rejects (7 > 5).
      // FIX: nonSepRank(6) = 5 -> clamp(5, 4) = 4 -> accepted.
      const modlistLines = [
        "+Sep1_separator",
        "+Sep2_separator",
        "+Sep3_separator",
        "+TargetSep_separator",
        "+Sep5_separator",
        "+Mod1",
        "+Mod2",
        "+Mod3",
        "+Mod4",
        "+BottomMod",
      ];
      await writeFile(
        join(root, "profiles", "Default", "modlist.txt"),
        modlistLines.join("\n") + "\n",
        "utf8",
      );
      await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
      await writeFile(
        join(root, "ModOrganizer.ini"),
        "[General]\ngame=fallout4\n[Settings]\nbase_directory=" + root + "\n",
        "utf8",
      );
      const brokerCalls: Array<{ method: string; payload: unknown }> = [];
      const ctx: ToolContext = {
        config: {
          mo2Root: root,
          permissionCeiling: "full-control",
          allowedProfiles: ["Default"],
          deny: [],
          snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
          auditRoot: join(root, ".mo2-mcp", "audit"),
        },
        sessionId: "test",
        plans: new PlanCache(),
        snapshots: new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "test"),
        audit: new AuditLogger(join(root, ".mo2-mcp", "audit"), "test"),
      };
      return { root, ctx, brokerCalls };
    }

    it("plan diff for above_separator quotes a priority within broker bounds", async () => {
      const { ctx } = await _fixtureWithSeparatorsOnTop();
      const tool = getTool("mo2_send_mod_to")!;
      const plan = (await tool.handler(
        {
          mode: "plan",
          name: "BottomMod",
          target_mode: "above_separator",
          target_separator: "TargetSep_separator",
        },
        ctx,
      )) as { ok: boolean; result: { diff: string } };
      expect(plan.ok).toBe(true);
      // Extract the integer priority from the diff string.
      const m = /priority\s+(\d+)/.exec(plan.result.diff);
      expect(m, `diff string did not include a priority: ${plan.result.diff}`).not.toBeNull();
      const planPri = Number(m![1]);
      // Broker max_priority = nonSep.length = 5; valid range [0..5].
      expect(planPri).toBeGreaterThanOrEqual(0);
      expect(planPri).toBeLessThanOrEqual(5);
      // For this fixture nonSepRank(6)=5 -> clamp to nonSep.length-1=4.
      expect(planPri).toBe(4);
    });

    it("apply round-trip: live broker receives broker-accepted priority", async () => {
      const { ctx, brokerCalls } = await _fixtureWithSeparatorsOnTop();
      ctx.pipeClient = {
        call: async (method: string, payload: unknown) => {
          brokerCalls.push({ method, payload });
          if (method === "profile.active")
            return { ok: true, result: { name: "Default" }, error: null };
          if (method === "mods.set_priority") {
            const p = payload as { priority: number };
            // Mirror the broker validator (mo2_agent_control.py:991):
            //   max_priority = max(0, len(non_separator_mods))  // here = 5
            //   if priority < 0 or priority > max_priority -> reject
            const maxPriority = 5;
            if (p.priority < 0 || p.priority > maxPriority) {
              return {
                ok: false,
                error: {
                  code: "priority_out_of_range",
                  message: `priority ${p.priority} out of [0..${maxPriority}]`,
                },
              };
            }
            return { ok: true, result: { actual_priority: p.priority }, error: null };
          }
          throw new Error(`unexpected broker method ${method}`);
        },
        close: () => {},
        discoverAndConnect: async () => {},
        isConnected: () => true,
      } as unknown as ToolContext["pipeClient"];
      const tool = getTool("mo2_send_mod_to")!;
      const planRes = (await tool.handler(
        {
          mode: "plan",
          name: "BottomMod",
          target_mode: "above_separator",
          target_separator: "TargetSep_separator",
        },
        ctx,
      )) as { ok: boolean; result: { plan_id: string; lease_token: string } };
      expect(planRes.ok).toBe(true);
      const applyRes = (await tool.handler(
        {
          mode: "apply",
          plan_id: planRes.result.plan_id,
          lease_token: planRes.result.lease_token,
        },
        ctx,
      )) as { ok: boolean; error?: { message: string } };
      expect(
        applyRes.ok,
        `apply rejected by broker: ${applyRes.error?.message ?? "(no error message)"}`,
      ).toBe(true);
      const setPri = brokerCalls.find((c) => c.method === "mods.set_priority");
      expect(setPri, "broker mods.set_priority was not called").toBeDefined();
      const p = setPri!.payload as { priority: number; name: string };
      expect(p.name).toBe("BottomMod");
      expect(p.priority).toBe(4);
    });
  });

  it("plan with target_mode=above_separator unknown separator throws", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_send_mod_to")!;
    await expect(
      tool.handler(
        {
          mode: "plan",
          name: "BottomMod",
          target_mode: "above_separator",
          target_separator: "NoSuch_separator",
        },
        ctx,
      ),
    ).rejects.toThrow(/separator_not_found/);
  });

  it("conflict modes throw without sidecar", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_send_mod_to")!;
    await expect(
      tool.handler(
        { mode: "plan", name: "BottomMod", target_mode: "above_first_conflict" },
        ctx,
      ),
    ).rejects.toThrow(/sidecar_required/);
  });

  // BUG-9 fix (2026-06-17): cross-profile request is rejected at plan time.
  it("BUG-9: live plan blocks when requested profile is not the active MO2 profile", async () => {
    const { ctx } = await _fixture();
    ctx.pipeClient = {
      call: async (method: string) => {
        if (method === "profile.active") return { ok: true, result: { name: "Default" }, error: null };
        throw new Error(`unexpected broker call during plan: ${method}`);
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
    const tool = getTool("mo2_send_mod_to")!;

    await expect(tool.handler(
      { mode: "plan", name: "BottomMod", target_mode: "top", profile: "BB84自用" },
      ctx,
    )).rejects.toThrow(/cross_profile_live_mutation_blocked/);
  });
});
