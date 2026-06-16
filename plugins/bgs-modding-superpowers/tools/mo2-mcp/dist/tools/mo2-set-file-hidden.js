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
import { routeToPlanApply } from "../plan-apply.js";
import { readMoIni } from "../mo-ini.js";
import { readProfile } from "../profile-reader.js";
import { invalidateWorld } from "./state-sync.js";
const inputSchema = z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), virtual_path: z.string(), hidden: z.boolean() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);
function _withoutDataPrefix(virtualPath) {
    return virtualPath.replace(/^Data[/\\]/i, "");
}
function _hidePath(realPath) {
    return realPath.endsWith(".mohidden") ? realPath : `${realPath}.mohidden`;
}
function _unhidePath(realPath) {
    return realPath.replace(/\.mohidden$/, "");
}
function _candidateRels(virtualPath) {
    const bases = [virtualPath, _withoutDataPrefix(virtualPath)];
    const expanded = bases.flatMap((rel) => rel.endsWith(".mohidden") ? [rel] : [rel, `${rel}.mohidden`]);
    return Array.from(new Set(expanded));
}
async function _resolveOffline(ctx, virtualPath) {
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    const profile = await readProfile(join(ctx.config.mo2Root, "profiles", "Default"));
    const enabled = profile.mods
        .filter((mod) => mod.enabled && !mod.isSeparator)
        .sort((a, b) => b.priority - a.priority);
    const rels = _candidateRels(virtualPath);
    for (const mod of enabled) {
        for (const rel of rels) {
            const direct = join(modsDir, mod.name, rel);
            if (existsSync(direct))
                return direct;
            const data = join(modsDir, mod.name, "Data", rel);
            if (existsSync(data))
                return data;
        }
    }
    throw new Error("file_not_found_in_enabled_mods");
}
async function _resolveRealPath(args, ctx, plan) {
    const virtualPath = args.virtual_path;
    if (ctx.pipeClient) {
        const resp = await ctx.pipeClient.call("organizer.resolve_path", { filename: virtualPath });
        if (!resp.ok)
            throw new Error(resp.error?.message ?? "organizer.resolve_path failed");
        const resolved = resp.result?.resolved;
        if (resolved)
            return resolved;
        throw new Error(`virtual_path_not_resolvable: ${virtualPath}`);
    }
    // The offline plan already leased the exact file path. Prefer that stable
    // path at apply time so visible→hidden / hidden→visible transitions remain
    // deterministic even after another same-name provider exists lower in order.
    if (plan)
        return plan.affectedFiles[0];
    return _resolveOffline(ctx, virtualPath);
}
function _transition(realPath, desiredHidden) {
    const isCurrentlyHidden = realPath.endsWith(".mohidden");
    return {
        isCurrentlyHidden,
        noOp: desiredHidden === isCurrentlyHidden,
        newPath: desiredHidden ? _hidePath(realPath) : _unhidePath(realPath),
    };
}
const handler = {
    toolName: "mo2_set_file_hidden",
    async buildPlan(args, ctx) {
        const realPath = await _resolveRealPath(args, ctx);
        const hidden = args.hidden;
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
        const hidden = plan.args.hidden;
        const state = _transition(realPath, hidden);
        if (state.noOp)
            return { no_op: true, path: realPath };
        await rename(realPath, state.newPath);
        await invalidateWorld(ctx, ["Default"]);
        return { renamed_from: realPath, renamed_to: state.newPath, hidden };
    },
};
registerTool({
    name: "mo2_set_file_hidden",
    tier: "T3",
    description: "Hide or unhide a VFS file via .mohidden rename (USVFS skipFileSuffixes convention). Only works on loose files (not archive entries).",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
