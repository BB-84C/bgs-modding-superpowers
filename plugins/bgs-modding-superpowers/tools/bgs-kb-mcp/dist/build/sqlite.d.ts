import type { PackMeta, SourceRecord } from "./types.js";
export interface DbHandle {
    exec(sql: string): void;
    prepare(sql: string): {
        run: (...args: unknown[]) => unknown;
        get: (...args: unknown[]) => unknown;
        all: (...args: unknown[]) => unknown;
    };
    close(): void;
}
export declare function openDb(path: string): DbHandle;
export declare function applySchema(db: DbHandle): void;
export declare function insertRecord(db: DbHandle, record: SourceRecord, packId: string): void;
export declare function writePackMeta(db: DbHandle, meta: PackMeta, recordCount: number, builtAt: string): void;
