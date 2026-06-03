export interface PrunePackSummary {
    packId: string;
    kept: string[];
    removed: string[];
}
export interface PruneCacheResult {
    cacheRoot: string;
    dryRun: boolean;
    packs: PrunePackSummary[];
}
export declare function pruneCache(cacheRoot: string, opts?: {
    dryRun?: boolean;
}): Promise<PruneCacheResult>;
export declare function formatPruneCacheResult(result: PruneCacheResult): string;
