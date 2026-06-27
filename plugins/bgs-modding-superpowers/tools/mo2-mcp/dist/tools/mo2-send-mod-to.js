/**
 * mo2_send_mod_to — T3 reposition a mod by GUI-aligned target mode.
 *
 * Vocabulary contract (mirrors MO2 GUI mods panel — BOTTOM wins):
 *   - gui_top              → priority 0 (top of GUI, loaded first, loses all)
 *   - gui_bottom           → priority N-1 (bottom of GUI, loaded last, wins all)
 *   - wins_over <anchor>   → anchor.priority + 1 (one slot ABOVE anchor in
 *                            precedence; one slot BELOW anchor visually in GUI;
 *                            if anchor is a separator, this is "into the section
 *                            labeled by that separator, at the section's top
 *                            visual position")
 *   - loses_to <anchor>    → anchor.priority - 1
 *   - wins_over_conflicts  → max(file-sharing mods' priorities) + 1
 *   - loses_to_conflicts   → min(file-sharing mods' priorities) - 1
 *   - raw_priority         → explicit mobase priority, clamped [0, mod_count-1]
 */
import { z } from "zod";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { atomicWriteText } from "../atomic.js";
import { readProfile } from "../profile-reader.js";
import { resolveProfileDir } from "../path-helpers.js";
import { assertActiveProfile } from "../profile-guard.js";
import { requireBoundContext } from "../binding.js";
import { invalidateWorld } from "./state-sync.js";
import { CONFLICT_PREVIEW_SIDECAR_SKIPPED, computeConflictDelta, conflictPreviewFromReport, isSidecarReport, previewOrUnavailable, reportForMod, } from "../conflict-preview.js";
import { logApplyEvent } from "../log-apply.js";
const ModeSchema = z.enum([
    "gui_top",
    "gui_bottom",
    "wins_over",
    "loses_to",
    "wins_over_conflicts",
    "loses_to_conflicts",
    "raw_priority",
]);
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        name: z.string().min(1),
        target_mode: ModeSchema,
        anchor: z.string().min(1).optional(),
        target_priority: z.number().int().optional(),
        profile: z.string().default("Default"),
    }).strict(),
    z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }).strict(),
]);
const RESPONSE_META = {
    priority_convention: "mobase_full_space_higher_wins",
    modlist_file_order: "reverse_of_gui",
    gui_direction_hint: "priority_0_at_gui_top_loses; priority_(N-1)_at_gui_bottom_wins",
};
async function _computeTargetPriority(args, ctx, profile) {
    const bound = requireBoundContext(ctx);
    const p = await readProfile(join(bound.config.mo2Root, "profiles", profile));
    const maxPri = Math.max(0, p.mods.length - 1);
    const clamp = (v) => Math.max(0, Math.min(v, maxPri));
    const mode = args.target_mode;
    switch (mode) {
        case "gui_top":
            return 0;
        case "gui_bottom":
            return maxPri;
        case "raw_priority": {
            const tp = args.target_priority;
            if (typeof tp !== "number" || !Number.isInteger(tp)) {
                throw new Error("raw_priority_requires_target_priority_int");
            }
            return clamp(tp);
        }
        case "wins_over":
        case "loses_to": {
            const anchorName = args.anchor;
            if (typeof anchorName !== "string" || anchorName.length === 0) {
                throw new Error(`${mode}_requires_anchor`);
            }
            const anchor = p.mods.find((m) => m.name === anchorName);
            if (!anchor)
                throw new Error(`anchor_not_found: ${anchorName}`);
            return clamp(mode === "wins_over" ? anchor.priority + 1 : anchor.priority - 1);
        }
        case "wins_over_conflicts":
        case "loses_to_conflicts": {
            const sidecar = bound.sidecar;
            if (!sidecar) {
                throw new Error("sidecar_required_for_conflict_mode");
            }
            const conflicts = (await sidecar.call("assets.conflicts", {
                profile_dir: join(bound.config.mo2Root, "profiles", profile),
                max_results: 5000,
            }));
            const conflictMods = (conflicts.conflicts ?? [])
                .filter((c) => c.providers?.includes(args.name))
                .flatMap((c) => (c.providers ?? []).filter((n) => n !== args.name));
            if (conflictMods.length === 0) {
                throw new Error("no_conflicts_found");
            }
            const conflictPris = conflictMods
                .map((n) => p.mods.find((m) => m.name === n))
                .filter((m) => m !== undefined && !m.isSeparator)
                .map((m) => m.priority);
            if (conflictPris.length === 0) {
                throw new Error("no_conflicts_found");
            }
            if (mode === "wins_over_conflicts")
                return clamp(Math.max(...conflictPris) + 1);
            return clamp(Math.min(...conflictPris) - 1);
        }
        default:
            throw new Error(`unknown_mode: ${mode}`);
    }
}
const handler = {
    toolName: "mo2_send_mod_to",
    async buildPlan(args, ctx) {
        const profile = args.profile ?? "Default";
        // BUG-9 fix (2026-06-17): refuse plan generation when MO2 is live on a
        // different profile (mirrors the apply-time check). Priority reorder
        // targets the requested profile's modlist.txt; planning against the
        // wrong profile produces a diff that does not match what apply would
        // later try to enforce.
        await assertActiveProfile(ctx, profile);
        const targetPri = await _computeTargetPriority(args, ctx, profile);
        const modlistPath = join(resolveProfileDir(ctx, profile), "modlist.txt");
        const bound = requireBoundContext(ctx);
        const p = await readProfile(join(bound.config.mo2Root, "profiles", profile));
        const maxPri = Math.max(0, p.mods.length - 1);
        const diffMeta = (() => {
            switch (args.target_mode) {
                case "gui_top": return "gui_top (priority 0 = loses all)";
                case "gui_bottom": return `gui_bottom (priority ${maxPri} = wins all)`;
                case "wins_over": return `wins_over ${args.anchor}`;
                case "loses_to": return `loses_to ${args.anchor}`;
                case "wins_over_conflicts": return "wins_over_conflicts (top of conflict set)";
                case "loses_to_conflicts": return "loses_to_conflicts (bottom of conflict set)";
                case "raw_priority": return `raw_priority ${args.target_priority}`;
                default: return String(args.target_mode);
            }
        })();
        return {
            diff: `${args.name}: → priority ${targetPri} (${diffMeta})`,
            affectedFiles: [modlistPath],
            targets: [{ path: modlistPath, kind: "text-file" }],
        };
    },
    async applyMutation(plan, ctx) {
        const bound = requireBoundContext(ctx);
        const args = plan.args;
        const profile = args.profile ?? "Default";
        const preReport = bound.sidecar
            ? await previewOrUnavailable(() => reportForMod(args.name, bound, profile))
            : undefined;
        if (bound.pipeClient) {
            await assertActiveProfile(ctx, profile);
            const targetPri = await _computeTargetPriority(args, ctx, profile);
            const resp = await bound.pipeClient.call("mods.set_priority", {
                name: args.name,
                priority: targetPri,
            });
            if (!resp.ok)
                throw new Error(resp.error?.message ?? "broker error");
            await invalidateWorld(ctx, [profile]);
            await logApplyEvent(handler.toolName, `moved "${args.name}" mode=${args.target_mode} anchor="${args.anchor ?? "none"}" priority→${targetPri}`, bound, plan.planId, profile);
            const postReport = bound.sidecar
                ? await previewOrUnavailable(() => reportForMod(args.name, bound, profile))
                : undefined;
            const conflictsPreview = bound.sidecar
                ? isSidecarReport(postReport)
                    ? conflictPreviewFromReport(postReport)
                    : postReport
                : CONFLICT_PREVIEW_SIDECAR_SKIPPED;
            const conflictsDelta = isSidecarReport(preReport) && isSidecarReport(postReport)
                ? computeConflictDelta(preReport, postReport)
                : undefined;
            return {
                ...resp.result,
                target_mode: args.target_mode,
                conflicts_preview: conflictsPreview,
                ...(conflictsDelta ? { conflicts_delta: conflictsDelta } : {}),
                _meta: RESPONSE_META,
            };
        }
        // Offline: rewrite modlist.txt line order
        const targetPri = await _computeTargetPriority(args, ctx, profile);
        const modlistPath = join(resolveProfileDir(ctx, profile), "modlist.txt");
        const text = await readFile(modlistPath, "utf8");
        const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
        const idx = lines.findIndex((l) => l.replace(/^[+\-]/, "") === args.name);
        if (idx < 0)
            throw new Error("mod_not_found_in_modlist");
        const [moved] = lines.splice(idx, 1);
        // priority N-1 = top of mobase = bottom of modlist.txt; convert
        const insertIdx = Math.max(0, Math.min(lines.length - targetPri, lines.length));
        lines.splice(insertIdx, 0, moved);
        await atomicWriteText(modlistPath, lines.join("\n") + "\n");
        await invalidateWorld(ctx, [profile]);
        await logApplyEvent(handler.toolName, `moved "${args.name}" mode=${args.target_mode} anchor="${args.anchor ?? "none"}" priority→${targetPri}`, bound, plan.planId, profile);
        const postReport = bound.sidecar
            ? await previewOrUnavailable(() => reportForMod(args.name, bound, profile))
            : undefined;
        const conflictsPreview = bound.sidecar
            ? isSidecarReport(postReport)
                ? conflictPreviewFromReport(postReport)
                : postReport
            : CONFLICT_PREVIEW_SIDECAR_SKIPPED;
        const conflictsDelta = isSidecarReport(preReport) && isSidecarReport(postReport)
            ? computeConflictDelta(preReport, postReport)
            : undefined;
        return {
            name: args.name,
            new_priority: targetPri,
            target_mode: args.target_mode,
            source: "offline_modlist_reorder",
            conflicts_preview: conflictsPreview,
            ...(conflictsDelta ? { conflicts_delta: conflictsDelta } : {}),
            _meta: RESPONSE_META,
        };
    },
};
registerTool({
    name: "mo2_send_mod_to",
    tier: "T3",
    description: "Reposition a mod by GUI-aligned mode: gui_top/gui_bottom/wins_over/loses_to/wins_over_conflicts/loses_to_conflicts/raw_priority.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
