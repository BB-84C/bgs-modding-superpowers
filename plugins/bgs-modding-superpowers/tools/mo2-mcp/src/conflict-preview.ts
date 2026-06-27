import { join } from "node:path";
import type { BoundContext } from "./binding.js";

export interface SidecarReport {
  mod: string;
  total_files: number;
  files_winning: number;
  files_losing: number;
  files_unique: number;
  overridden_by: Array<{ mod: string; files: number }>;
  overrides: Array<{ mod: string; files: number }>;
  winners_by_file: Record<string, string>;
}

export interface ConflictPreview {
  mod: string;
  files_total: number;
  files_winning: number;
  files_losing: number;
  files_unique: number;
  top_overridden_by: Array<{mod: string; files: number}>;
  top_overrides: Array<{mod: string; files: number}>;
}

export interface ConflictDelta {
  files_winner_changed: number;
  newly_winning: number;
  newly_losing: number;
  affected_mods: Array<{mod: string; flipped_files: number; direction: "now_loses_to_us" | "now_beats_us"}>;
  message?: string;
}

export interface ConflictPreviewRemoved {
  removed: true;
  files_no_longer_provided: number;
  top_affected: Array<{mod: string; files: number}>;
}

export function isSidecarReport(value: unknown): value is SidecarReport {
  return typeof value === "object"
    && value !== null
    && typeof (value as { mod?: unknown }).mod === "string"
    && typeof (value as { total_files?: unknown }).total_files === "number"
    && typeof (value as { winners_by_file?: unknown }).winners_by_file === "object";
}

function topFive(entries: Array<{ mod: string; files: number }>): Array<{ mod: string; files: number }> {
  return [...entries]
    .sort((a, b) => b.files - a.files || a.mod.localeCompare(b.mod))
    .slice(0, 5);
}

export async function reportForMod(
  modName: string,
  ctx: BoundContext,
  profile: string,
): Promise<SidecarReport> {
  if (!ctx.sidecar) throw new Error("sidecar_not_bound");
  return await ctx.sidecar.call("assets.report_for_mod", {
    profile_dir: join(ctx.config.mo2Root, "profiles", profile),
    mod_name: modName,
  }) as SidecarReport;
}

export async function computeConflictPreview(
  modName: string,
  ctx: BoundContext,
  profile: string,
): Promise<ConflictPreview> {
  const report = await reportForMod(modName, ctx, profile);
  return conflictPreviewFromReport(report);
}

export function conflictPreviewFromReport(report: SidecarReport): ConflictPreview {
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

function addAffected(
  affected: Map<string, { mod: string; flipped_files: number; direction: "now_loses_to_us" | "now_beats_us" }>,
  mod: string | undefined,
  direction: "now_loses_to_us" | "now_beats_us",
): void {
  if (!mod) return;
  const key = `${direction}\u0000${mod}`;
  const existing = affected.get(key);
  if (existing) {
    existing.flipped_files += 1;
    return;
  }
  affected.set(key, { mod, flipped_files: 1, direction });
}

export function computeConflictDelta(pre: SidecarReport, post: SidecarReport): ConflictDelta {
  const files = new Set<string>([
    ...Object.keys(pre.winners_by_file ?? {}),
    ...Object.keys(post.winners_by_file ?? {}),
  ]);
  let filesWinnerChanged = 0;
  let newlyWinning = 0;
  let newlyLosing = 0;
  const affected = new Map<string, { mod: string; flipped_files: number; direction: "now_loses_to_us" | "now_beats_us" }>();

  for (const file of files) {
    const preWinner = pre.winners_by_file?.[file];
    const postWinner = post.winners_by_file?.[file];
    if (preWinner === postWinner) continue;
    filesWinnerChanged += 1;
    if (preWinner !== pre.mod && postWinner === post.mod) {
      newlyWinning += 1;
      addAffected(affected, preWinner, "now_loses_to_us");
    } else if (preWinner === pre.mod && postWinner !== post.mod) {
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
      .sort((a, b) => (
        b.flipped_files - a.flipped_files
        || (a.direction === b.direction ? 0 : a.direction === "now_loses_to_us" ? -1 : 1)
        || a.mod.localeCompare(b.mod)
      ))
      .slice(0, 5),
  };
}

export function computeRemovedPreview(pre: SidecarReport): ConflictPreviewRemoved {
  return {
    removed: true,
    files_no_longer_provided: pre.total_files,
    top_affected: topFive(pre.overrides),
  };
}

export async function previewOrUnavailable<T>(fn: () => Promise<T>): Promise<T | { error: "preview_unavailable"; reason: string }> {
  try {
    return await fn();
  } catch (error) {
    return {
      error: "preview_unavailable",
      reason: error instanceof Error ? error.message : String(error),
    };
  }
}

export const CONFLICT_PREVIEW_SIDECAR_SKIPPED = { skipped: "sidecar_not_bound" } as const;
