import { createRequire } from "node:module";
// Vitest/Vite have trouble with static `import { DatabaseSync } from "node:sqlite"`.
// Mirror the workaround used in src/build/sqlite.ts. createRequire returns the
// real Node built-in, not the test runner's mock.
const require_ = createRequire(import.meta.url);
const sqlite = require_("node:sqlite");
/**
 * Open a kb.sqlite at the given path in read-only mode.
 * Throws if the file cannot be opened or the file is not a valid SQLite database.
 */
export function openReadOnly(kbSqlitePath) {
    return new sqlite.DatabaseSync(kbSqlitePath, { readOnly: true });
}
//# sourceMappingURL=sqlite-loader.js.map