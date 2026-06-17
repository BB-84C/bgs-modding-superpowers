/**
 * mo2_set_file_hidden — T3 loose-file hide/unhide via .mohidden suffix.
 *
 * USVFS/MO2 convention: files ending in .mohidden are skipped from the VFS.
 * This tool only operates on loose files, never archive entries.
 */
import { z } from "zod";
import { existsSync } from "node:fs";
import { rename } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler, type PlanRecord } from "../plan-apply.js";
import { readMoIni } from "../mo-ini.js";
import { readProfile } from "../profile-reader.js";
import type { ToolContext } from "../types.js";
import { invalidateWorld } from "./state-sync.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";

// BUG-10 fix (2026-06-17): virtual_path + plan_id + lease_token gain .min(1).
const inputSchema = z.discriminatedUnion("mode", [
  z.object({ mode: z.literal("plan"), virtual_path: z.string().min(1), hidden: z.boolean() }),
  z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);

function _withoutDataPrefix(virtualPath: string): string {
  return virtualPath.replace(/^Data[/\\]/i, "");
}

function _hidePath(realPath: string): string {
  return realPath.endsWith(".mohidden") ? realPath : `${realPath}.mohidden`;
}

function _unhidePath(realPath: string): string {
  return realPath.replace(/\.mohidden$/, "");
}

function _candidateRels(virtualPath: string): string[] {
  const bases = [virtualPath, _withoutDataPrefix(virtualPath)];
  const expanded = bases.flatMap((rel) => rel.endsWith(".mohidden") ? [rel] : [rel, `${rel}.mohidden`]);
  return Array.from(new Set(expanded));
}

async function _resolveOffline(ctx: ToolContext, virtualPath: string): Promise<string> {
  const bound = requireBoundContext(ctx);
  const ini = await readMoIni(join(bound.config.mo2Root, "ModOrganizer.ini"));
  const modsDir = ini.settings.modDirectory ?? join(bound.config.mo2Root, "mods");
  const profile = await readProfile(join(bound.config.mo2Root, "profiles", "Default"));
  const enabled = profile.mods
    .filter((mod) => mod.enabled && !mod.isSeparator)
    .sort((a, b) => b.priority - a.priority);
  const rels = _candidateRels(virtualPath);

  for (const mod of enabled) {
    for (const rel of rels) {
      const direct = join(modsDir, mod.name, rel);
      if (existsSync(direct)) return direct;
      const data = join(modsDir, mod.name, "Data", rel);
      if (existsSync(data)) return data;
    }
  }
  throw new Error("file_not_found_in_enabled_mods");
}

async function _resolveRealPath(
  args: Record<string, unknown>,
  ctx: ToolContext,
  plan?: PlanRecord,
): Promise<string> {
  const virtualPath = args.virtual_path as string;
  const pipeClient = requireBoundContext(ctx).pipeClient;
  if (pipeClient) {
    const resp = await pipeClient.call("organizer.resolve_path", { filename: virtualPath }) as {
      ok: boolean;
      result?: { resolved?: string | null };
      error?: { message?: string } | null;
    };
    if (!resp.ok) throw new Error(resp.error?.message ?? "organizer.resolve_path failed");
    const resolved = resp.result?.resolved;
    if (resolved) return resolved;
    // Broker live resolve can legitimately miss files that were created by test
    // fixtures or external fs writes after MO2 startup. Fall back to the
    // offline scan before declaring the path unresolvable.
    if (plan) return plan.affectedFiles[0];
    return _resolveOffline(ctx, virtualPath);
  }
  // The offline plan already leased the exact file path. Prefer that stable
  // path at apply time so visible→hidden / hidden→visible transitions remain
  // deterministic even after another same-name provider exists lower in order.
  if (plan) return plan.affectedFiles[0];
  return _resolveOffline(ctx, virtualPath);
}

function _transition(realPath: string, desiredHidden: boolean): {
  isCurrentlyHidden: boolean;
  noOp: boolean;
  newPath: string;
} {
  const isCurrentlyHidden = realPath.endsWith(".mohidden");
  return {
    isCurrentlyHidden,
    noOp: desiredHidden === isCurrentlyHidden,
    newPath: desiredHidden ? _hidePath(realPath) : _unhidePath(realPath),
  };
}

const handler: PlanApplyHandler = {
  toolName: "mo2_set_file_hidden",
  async buildPlan(args, ctx) {
    const realPath = await _resolveRealPath(args, ctx);
    const hidden = args.hidden as boolean;
    const state = _transition(realPath, hidden);
    if (state.noOp) {
      return {
        diff: `no-op (already ${hidden ? "hidden" : "visible"})`,
        affectedFiles: [realPath],
        targets: [{ path: realPath, kind: "text-file" }],
      };
    }
    return {
      diff: `${realPath} → ${state.newPath}`,
      affectedFiles: [realPath, state.newPath],
      targets: [{ path: realPath, kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    const realPath = await _resolveRealPath(plan.args, ctx, plan);
    const hidden = plan.args.hidden as boolean;
    const state = _transition(realPath, hidden);
    if (state.noOp) return { no_op: true, path: realPath };

    await rename(realPath, state.newPath);
    await invalidateWorld(ctx, ["Default"]);
    return { renamed_from: realPath, renamed_to: state.newPath, hidden };
  },
};

registerTool({
  name: "mo2_set_file_hidden",
  tier: "T3",
  description:
    "Hide or unhide a VFS file via .mohidden rename (USVFS skipFileSuffixes convention). Only works on loose files (not archive entries).",
  inputSchema,
  handler: (args, ctx) =>
    routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
