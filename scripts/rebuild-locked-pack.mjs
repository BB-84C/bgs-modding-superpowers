#!/usr/bin/env node
// scripts/rebuild-locked-pack.mjs
//
// Rebuilds a KB pack's kb.sqlite + manifest.json IN PLACE without unlinking
// kb.sqlite first. This is the workaround when a non-Node Windows process
// (Defender / Search Indexer / sync client) holds an open handle on the
// SQLite file with FILE_SHARE_READ + FILE_SHARE_WRITE but NOT
// FILE_SHARE_DELETE — write succeeds, but `rm` fails with EBUSY.
//
// Mirrors tools/bgs-kb-mcp/dist/build/index.js (buildPack) exactly except
// for the rm step, which is replaced by a "drop all user-created schema
// objects" pass against the existing file.
//
// Usage:
//   node scripts/rebuild-locked-pack.mjs <pack-root>
//
// Example:
//   node scripts/rebuild-locked-pack.mjs knowledge/bgs-kb/packs/core
//
// Exit codes:
//   0  success
//   1  validation error (records do not match schema)
//   2  infrastructure error (IO / SQLite open failure)
//
// This is a maintenance utility, not part of the normal build flow.
// The permanent fix for the build module's unlink-then-recreate strategy
// can land separately; this script unblocks the immediate rebuild needs.

import { createRequire } from "node:module";
import { resolve, join } from "node:path";

const require_ = createRequire(import.meta.url);
const { DatabaseSync } = require_("node:sqlite");

const packRootArg = process.argv[2];
if (!packRootArg) {
  console.error("Usage: node scripts/rebuild-locked-pack.mjs <pack-root>");
  process.exit(2);
}

const packRoot = resolve(packRootArg);
console.log(`[rebuild-locked-pack] rebuilding (in-place, no unlink): ${packRoot}`);

let buildModule, manifestModule, readRecordsModule, sqliteModule, validateModule;
try {
  // Import the existing build module's pieces from dist/
  buildModule = await import("../tools/bgs-kb-mcp/dist/build/index.js");
  manifestModule = await import("../tools/bgs-kb-mcp/dist/build/manifest.js");
  readRecordsModule = await import("../tools/bgs-kb-mcp/dist/build/read-records.js");
  sqliteModule = await import("../tools/bgs-kb-mcp/dist/build/sqlite.js");
  validateModule = await import("../tools/bgs-kb-mcp/dist/build/validate.js");
} catch (err) {
  console.error(`[rebuild-locked-pack] failed to import bgs-kb-mcp build modules: ${err.message}`);
  console.error("[rebuild-locked-pack] is tools/bgs-kb-mcp/dist/ built? run `npm run build` there first.");
  process.exit(2);
}

const { buildManifest, readPackMeta, sha256File, writeManifest } = manifestModule;
const { readRecords } = readRecordsModule;
const { applySchema, insertRecord, writePackMeta } = sqliteModule;
const { validateRecords } = validateModule;
const { BuildValidationError } = buildModule;

let records;
try {
  records = await readRecords(packRoot);
} catch (err) {
  console.error(`[rebuild-locked-pack] readRecords failed: ${err.message}`);
  process.exit(2);
}

const validation = validateRecords(records, packRoot);
if (validation.errors.length > 0) {
  console.error(`[rebuild-locked-pack] validation failed for ${validation.errors.length} record(s):`);
  for (const e of validation.errors) {
    console.error(`  ${e.sourcePath ?? "<unknown>"}: ${JSON.stringify(e)}`);
  }
  process.exit(1);
}

const meta = await readPackMeta(packRoot);
const builtAt = new Date().toISOString();
const kbPath = join(packRoot, "kb.sqlite");

let db;
try {
  // Open the existing file (or create if missing). Write mode — no unlink.
  db = new DatabaseSync(kbPath, { readOnly: false });
  db.exec("PRAGMA foreign_keys = ON");
  // 60s busy_timeout: when another process briefly grabs an OS-level file
  // lock on kb.sqlite (Defender scan, indexer, sync client), SQLITE_BUSY
  // (errcode 5) surfaces inside COMMIT. Retrying for up to 60s lets the
  // other process release.
  db.exec("PRAGMA busy_timeout = 60000");
} catch (err) {
  console.error(`[rebuild-locked-pack] failed to open ${kbPath}: ${err.message}`);
  process.exit(2);
}

try {
  // === Drop all user-created schema objects ===
  // Enumerate sqlite_master, filter to objects we created (sql IS NOT NULL
  // and not internal sqlite_* names), drop in dependency-safe order:
  //   triggers -> views -> indexes -> tables (virtual + regular)
  // FTS5 virtual table's shadow tables (records_fts_data, records_fts_idx,
  // etc.) get cleaned up automatically when the virtual table drops.
  const dropRows = db
    .prepare(
      "SELECT type, name FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' " +
        "ORDER BY CASE type WHEN 'trigger' THEN 1 WHEN 'view' THEN 2 WHEN 'index' THEN 3 ELSE 4 END",
    )
    .all();

  db.exec("BEGIN");
  for (const { type, name } of dropRows) {
    // type is one of: trigger, view, index, table.
    const safeName = String(name).replace(/"/g, '""');
    db.exec(`DROP ${String(type).toUpperCase()} IF EXISTS "${safeName}"`);
  }
  db.exec("COMMIT");

  console.log(`[rebuild-locked-pack]   dropped ${dropRows.length} existing schema objects`);

  // === Re-apply schema + repopulate ===
  applySchema(db);
  writePackMeta(db, meta, validation.valid.length, builtAt);

  // insertRecord wraps each row in its own BEGIN/COMMIT (per the build
  // module's idempotency model). We cannot nest a single outer transaction
  // here. Instead the 60s busy_timeout set above lets each per-row COMMIT
  // retry while an external process holds an OS-level lock, then fall
  // through cleanly once the other process releases.
  for (const record of validation.valid) {
    insertRecord(db, record, meta.packId);
  }

  // Sanity readback
  const count = db.prepare("SELECT COUNT(*) AS n FROM records").get();
  console.log(`[rebuild-locked-pack]   inserted ${count.n} records into kb.sqlite`);
} finally {
  db.close();
}

// === Manifest ===
const sha256 = await sha256File(kbPath);
const manifest = await buildManifest({
  packRoot,
  records: validation.valid,
  meta,
  builtAt,
  sha256,
});
const manifestPath = await writeManifest(packRoot, manifest);

console.log(`[rebuild-locked-pack] DONE`);
console.log(`[rebuild-locked-pack]   packId:        ${meta.packId}`);
console.log(`[rebuild-locked-pack]   recordCount:   ${validation.valid.length}`);
console.log(`[rebuild-locked-pack]   kb.sqlite:     ${kbPath} (sha256 ${sha256.slice(0, 12)}…)`);
console.log(`[rebuild-locked-pack]   manifest.json: ${manifestPath}`);
