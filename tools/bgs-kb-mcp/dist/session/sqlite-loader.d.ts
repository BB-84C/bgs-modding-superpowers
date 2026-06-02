export type DatabaseHandle = {
    prepare(sql: string): StatementHandle;
    close(): void;
};
export type StatementHandle = {
    all<T = unknown>(...params: unknown[]): T[];
    get<T = unknown>(...params: unknown[]): T | undefined;
};
/**
 * Open a kb.sqlite at the given path in read-only mode.
 * Throws if the file cannot be opened or the file is not a valid SQLite database.
 */
export declare function openReadOnly(kbSqlitePath: string): DatabaseHandle;
