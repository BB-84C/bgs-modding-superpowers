import { createRequire } from "node:module";

// Vitest/Vite have trouble with static `import { DatabaseSync } from "node:sqlite"`.
// Mirror the workaround used in src/build/sqlite.ts. createRequire returns the
// real Node built-in, not the test runner's mock.
const require_ = createRequire(import.meta.url);
const sqlite = require_("node:sqlite") as {
  DatabaseSync: new (path: string, opts?: { readOnly?: boolean }) => DatabaseHandle;
};

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
export function openReadOnly(kbSqlitePath: string): DatabaseHandle {
  return new sqlite.DatabaseSync(kbSqlitePath, { readOnly: true });
}
