import type { PackManifest } from "./types.js";
import { type RecordValidationError } from "./validate.js";
export interface BuildResult {
    packRoot: string;
    recordCount: number;
    kbSqlitePath: string;
    manifestPath: string;
    sha256: string;
    builtAt: string;
    manifest: PackManifest;
}
export declare class BuildValidationError extends Error {
    readonly validationErrors: RecordValidationError[];
    constructor(validationErrors: RecordValidationError[]);
}
export declare function buildPack(packRoot: string): Promise<BuildResult>;
