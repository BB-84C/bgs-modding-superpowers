/**
 * mo2_toggle_mod — T3 enable/disable mod.
 *
 * Live: broker mods.set_active.
 * Offline: modlist.txt atomic rewrite (find line ending with mod name, swap +/-).
 *
 * Lease is on modlist.txt content hash (T3 + plan/apply mandatory).
 */
import { z } from "zod";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { atomicWriteText } from "../atomic.js";
import { readProfile } from "../profile-reader.js";
import { resolveProfileDir } from "../path-helpers.js";
import { assertActiveProfile } from "../profile-guard.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";

// BUG-10 fix (2026-06-17): name+plan_id+lease_token gain .min(1) so empty
// strings fail Zod safeParse and reach the caller as the stable
// invalid_arguments envelope instead of falling through to the handler's
// `mod_not_found:` internal_error.
const inputSchema = z.discriminatedUnion("mode", [
  z.object({
    mode: z.literal("plan"),
    name: z.string().min(1),
    enabled: z.boolean(),
    profile: z.string().default("Default"),
  }),
  z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);

const handler: PlanApplyHandler = {
  toolName: "mo2_toggle_mod",
  async buildPlan(args, ctx) {
    const profile = (args.profile as string) ?? "Default";
    // BUG-9 fix (2026-06-17): refuse plan generation when MO2 is live on a
    // different profile. The active-profile guard was only firing at apply
    // time, which let the planner mint a plan_id + lease_token + diff that
    // referenced a non-active profile's modlist.txt; agents then carried
    // that misleading plan forward. assertActiveProfile is a no-op when
    // MO2 is offline (pipeClient absent).
    await assertActiveProfile(ctx, profile);
    const profileDir = resolveProfileDir(ctx, profile);
    const modlistPath = join(profileDir, "modlist.txt");
    const p = await readProfile(profileDir);
    const mod = p.mods.find((m) => m.name === args.name);
    if (!mod) {
      throw new Error(`mod_not_found: ${args.name}`);
    }
    if (mod.enabled === args.enabled) {
      return {
        diff: `no-op (${args.name} already ${args.enabled ? "enabled" : "disabled"})`,
        affectedFiles: [modlistPath],
        targets: [{ path: modlistPath, kind: "text-file" }],
      };
    }
    return {
      diff: `${args.name}: ${mod.enabled ? "+" : "-"} → ${args.enabled ? "+" : "-"}`,
      affectedFiles: [modlistPath],
      targets: [{ path: modlistPath, kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    const bound = requireBoundContext(ctx);
    const args = plan.args;
    const profile = (args.profile as string) ?? "Default";
    if (bound.pipeClient) {
      await assertActiveProfile(ctx, profile);
      const resp = await bound.pipeClient.call("mods.set_active", {
        names: [args.name],
        active: args.enabled,
      });
      if (!resp.ok) throw new Error(resp.error?.message ?? "broker error");
      return resp.result as Record<string, unknown>;
    }
    const modlistPath = join(resolveProfileDir(ctx, profile), "modlist.txt");
    const text = await readFile(modlistPath, "utf8");
    const lines = text.split(/\r?\n/);
    const newLines = lines.map((l) => {
      if (!l) return l;
      const bare = l.replace(/^[+\-]/, "");
      if (bare === (args.name as string) && !bare.endsWith("_separator")) {
        return (args.enabled ? "+" : "-") + (args.name as string);
      }
      return l;
    });
    await atomicWriteText(modlistPath, newLines.join("\n"));
    return {
      name: args.name,
      enabled: args.enabled,
      source: "offline_modlist_rewrite",
    };
  },
};

registerTool({
  name: "mo2_toggle_mod",
  tier: "T3",
  description:
    "Enable or disable a mod. Plan/apply with lease on modlist.txt content hash. Live: broker pipe; offline: atomic file rewrite.",
  inputSchema,
  handler: (args, ctx) =>
    routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
