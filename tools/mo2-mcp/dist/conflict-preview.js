import { join } from "node:path";
export function isSidecarReport(value) {
    return typeof value === "object"
        && value !== null
        && typeof value.mod === "string"
        && typeof value.total_files === "number"
        && typeof value.winners_by_file === "object";
}
function topFive(entries) {
    return [...entries]
        .sort((a, b) => b.files - a.files || a.mod.localeCompare(b.mod))
        .slice(0, 5);
}
export async function reportForMod(modName, ctx, profile) {
    if (!ctx.sidecar)
        throw new Error("sidecar_not_bound");
    return await ctx.sidecar.call("assets.report_for_mod", {
        profile_dir: join(ctx.config.mo2Root, "profiles", profile),
        mod_name: modName,
    });
}
export async function computeConflictPreview(modName, ctx, profile) {
    const report = await reportForMod(modName, ctx, profile);
    return conflictPreviewFromReport(report);
}
export function conflictPreviewFromReport(report) {
    return {
        mod: report.mod,
        files_total: report.total_files,
        files_winning: report.files_winning,
        files_losing: report.files_losing,
        files_unique: report.files_unique,
        top_overridden_by: topFive(report.overridden_by),
        top_overrides: topFive(report.overrides),
    };
}
function addAffected(affected, mod, direction) {
    if (!mod)
        return;
    const key = `${direction}\u0000${mod}`;
    const existing = affected.get(key);
    if (existing) {
        existing.flipped_files += 1;
        return;
    }
    affected.set(key, { mod, flipped_files: 1, direction });
}
export function computeConflictDelta(pre, post) {
    const files = new Set([
        ...Object.keys(pre.winners_by_file ?? {}),
        ...Object.keys(post.winners_by_file ?? {}),
    ]);
    let filesWinnerChanged = 0;
    let newlyWinning = 0;
    let newlyLosing = 0;
    const affected = new Map();
    for (const file of files) {
        const preWinner = pre.winners_by_file?.[file];
        const postWinner = post.winners_by_file?.[file];
        if (preWinner === postWinner)
            continue;
        filesWinnerChanged += 1;
        if (preWinner !== pre.mod && postWinner === post.mod) {
            newlyWinning += 1;
            addAffected(affected, preWinner, "now_loses_to_us");
        }
        else if (preWinner === pre.mod && postWinner !== post.mod) {
            newlyLosing += 1;
            addAffected(affected, postWinner, "now_beats_us");
        }
    }
    if (filesWinnerChanged === 0) {
        return {
            files_winner_changed: 0,
            newly_winning: 0,
            newly_losing: 0,
            affected_mods: [],
            message: "No conflict winner changes from this mutation",
        };
    }
    return {
        files_winner_changed: filesWinnerChanged,
        newly_winning: newlyWinning,
        newly_losing: newlyLosing,
        affected_mods: [...affected.values()]
            .sort((a, b) => (b.flipped_files - a.flipped_files
            || (a.direction === b.direction ? 0 : a.direction === "now_loses_to_us" ? -1 : 1)
            || a.mod.localeCompare(b.mod)))
            .slice(0, 5),
    };
}
export function computeRemovedPreview(pre) {
    return {
        removed: true,
        files_no_longer_provided: pre.total_files,
        top_affected: topFive(pre.overrides),
    };
}
export async function previewOrUnavailable(fn) {
    try {
        return await fn();
    }
    catch (error) {
        return {
            error: "preview_unavailable",
            reason: error instanceof Error ? error.message : String(error),
        };
    }
}
export const CONFLICT_PREVIEW_SIDECAR_SKIPPED = { skipped: "sidecar_not_bound" };
