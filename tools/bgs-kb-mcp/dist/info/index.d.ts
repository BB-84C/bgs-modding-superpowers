import type { PackManifest } from "../build/types.js";
export interface SqliteInfo {
    path: string;
    sizeBytes: number;
    sha256: string;
    sha256Verified?: boolean;
    recordCount: number;
}
export interface PackInfo {
    packRoot: string;
    manifestPath: string;
    sqlitePath: string;
    manifest?: PackManifest;
    sqlite?: SqliteInfo;
    warnings: string[];
    derivedRecordCount: number;
    domains: string[];
    games: string[];
    engineFamilies: string[];
    byDomain: Record<string, number>;
    byGame: Record<string, number>;
}
export declare function gatherInfo(packRoot: string): Promise<PackInfo>;
export declare function fallbackPackId(info: PackInfo): string;
