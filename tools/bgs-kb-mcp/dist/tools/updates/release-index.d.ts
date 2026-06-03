import { z } from "zod";
export declare const DEFAULT_LATEST_RELEASE_API_URL = "https://api.github.com/repos/BB-84C/bgs-modding-superpowers/releases/latest";
export declare const DEFAULT_RELEASE_DOWNLOAD_BASE = "https://github.com/BB-84C/bgs-modding-superpowers/releases/download";
declare const PackEntrySchema: z.ZodObject<{
    packId: z.ZodString;
    version: z.ZodString;
    schemaVersion: z.ZodNumber;
    minPluginVersion: z.ZodString;
    releaseUrl: z.ZodString;
    sha256: z.ZodString;
    sizeBytes: z.ZodNumber;
}, "strict", z.ZodTypeAny, {
    sha256: string;
    packId: string;
    version: string;
    schemaVersion: number;
    minPluginVersion: string;
    releaseUrl: string;
    sizeBytes: number;
}, {
    sha256: string;
    packId: string;
    version: string;
    schemaVersion: number;
    minPluginVersion: string;
    releaseUrl: string;
    sizeBytes: number;
}>;
declare const ReleaseIndexSchema: z.ZodObject<{
    releaseTag: z.ZodString;
    publishedAt: z.ZodString;
    packs: z.ZodArray<z.ZodObject<{
        packId: z.ZodString;
        version: z.ZodString;
        schemaVersion: z.ZodNumber;
        minPluginVersion: z.ZodString;
        releaseUrl: z.ZodString;
        sha256: z.ZodString;
        sizeBytes: z.ZodNumber;
    }, "strict", z.ZodTypeAny, {
        sha256: string;
        packId: string;
        version: string;
        schemaVersion: number;
        minPluginVersion: string;
        releaseUrl: string;
        sizeBytes: number;
    }, {
        sha256: string;
        packId: string;
        version: string;
        schemaVersion: number;
        minPluginVersion: string;
        releaseUrl: string;
        sizeBytes: number;
    }>, "many">;
}, "strict", z.ZodTypeAny, {
    packs: {
        sha256: string;
        packId: string;
        version: string;
        schemaVersion: number;
        minPluginVersion: string;
        releaseUrl: string;
        sizeBytes: number;
    }[];
    releaseTag: string;
    publishedAt: string;
}, {
    packs: {
        sha256: string;
        packId: string;
        version: string;
        schemaVersion: number;
        minPluginVersion: string;
        releaseUrl: string;
        sizeBytes: number;
    }[];
    releaseTag: string;
    publishedAt: string;
}>;
export type ReleaseIndex = z.infer<typeof ReleaseIndexSchema>;
export type ReleaseIndexEntry = z.infer<typeof PackEntrySchema>;
export interface ReleaseIndexFetcherOptions {
    fetchImpl?: typeof fetch;
    latestReleaseApiUrl?: string;
    manifestIndexUrl?: string;
    timeoutMs?: number;
}
export declare function fetchReleaseIndex(options?: ReleaseIndexFetcherOptions): Promise<ReleaseIndex>;
export {};
