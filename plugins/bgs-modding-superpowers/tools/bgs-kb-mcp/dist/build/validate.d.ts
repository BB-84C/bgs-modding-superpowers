import type { ErrorObject } from "ajv/dist/2020.js";
import type { SourceRecord } from "./types.js";
export interface RecordValidationError {
    sourcePath: string;
    errors: ErrorObject[];
}
export interface ValidateRecordsResult {
    valid: SourceRecord[];
    errors: RecordValidationError[];
}
export declare function findRepoRoot(startPath: string): string | null;
export declare function defaultSchemaPathForPack(packRoot: string): string;
export declare function validateRecords(records: SourceRecord[], packRoot: string, schemaPath?: string): ValidateRecordsResult;
export declare function formatValidationError(sourcePath: string, error: ErrorObject): string;
