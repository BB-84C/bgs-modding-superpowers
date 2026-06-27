import type { BoundContext } from "./binding.js";
export interface SidecarReport {
    mod: string;
    total_files: number;
    files_winning: number;
    files_losing: number;
    files_unique: number;
    overridden_by: Array<{
        mod: string;
        files: number;
    }>;
    overrides: Array<{
        mod: string;
        files: number;
    }>;
    winners_by_file: Record<string, string>;
}
export interface ConflictPreview {
    mod: string;
    files_total: number;
    files_winning: number;
    files_losing: number;
    files_unique: number;
    top_overridden_by: Array<{
        mod: string;
        files: number;
    }>;
    top_overrides: Array<{
        mod: string;
        files: number;
    }>;
}
export interface ConflictDelta {
    files_winner_changed: number;
    newly_winning: number;
    newly_losing: number;
    affected_mods: Array<{
        mod: string;
        flipped_files: number;
        direction: "now_loses_to_us" | "now_beats_us";
    }>;
    message?: string;
}
export interface ConflictPreviewRemoved {
    removed: true;
    files_no_longer_provided: number;
    top_affected: Array<{
        mod: string;
        files: number;
    }>;
}
export declare function isSidecarReport(value: unknown): value is SidecarReport;
export declare function reportForMod(modName: string, ctx: BoundContext, profile: string): Promise<SidecarReport>;
export declare function computeConflictPreview(modName: string, ctx: BoundContext, profile: string): Promise<ConflictPreview>;
export declare function conflictPreviewFromReport(report: SidecarReport): ConflictPreview;
export declare function computeConflictDelta(pre: SidecarReport, post: SidecarReport): ConflictDelta;
export declare function computeRemovedPreview(pre: SidecarReport): ConflictPreviewRemoved;
export declare function previewOrUnavailable<T>(fn: () => Promise<T>): Promise<T | {
    error: "preview_unavailable";
    reason: string;
}>;
export declare const CONFLICT_PREVIEW_SIDECAR_SKIPPED: {
    readonly skipped: "sidecar_not_bound";
};
