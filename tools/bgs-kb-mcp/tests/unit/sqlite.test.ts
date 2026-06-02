import { rm } from "node:fs/promises";
import { join } from "node:path";
import { afterEach, expect, test } from "vitest";

import { applySchema, insertRecord, openDb, writePackMeta } from "../../src/build/sqlite.js";
import type { SourceRecord } from "../../src/build/types.js";
import { cleanupTempPacks, makeTempPack } from "./test-helpers.js";

afterEach(cleanupTempPacks);

function sourceRecord(id: string, term: string, domains: string[] = ["xedit"]): SourceRecord {
  return {
    sourcePath: `records/${id.replaceAll(".", "/")}.md`,
    id,
    title: `${term} title`,
    domains,
    appliesTo: { games: ["Fallout4"], engineFamilies: ["creation-engine"] },
    canonical: { answer: `${term} canonical answer for sqlite tests.`, confidence: "verified-project-doc" },
    queryKeys: [term],
    sources: [{ kind: "project-internal-doc", ref: "tests/unit/sqlite.test.ts" }],
    lastReviewed: "2026-06-02",
    schemaVersion: 1,
    bodyMd: `# ${term}\n\nBody contains ${term}.`,
  };
}

test("SQLite schema, inserts, join tables, and FTS triggers work", async () => {
  const packRoot = await makeTempPack("kb-sqlite-");
  const dbPath = join(packRoot, "kb.sqlite");
  await rm(dbPath, { force: true });
  const db = openDb(dbPath);
  try {
    applySchema(db);
    writePackMeta(
      db,
      { packId: "test-pack", displayName: "Test Pack", version: "2026.06.02", schemaVersion: 1, minPluginVersion: "0.2.0", owner: "tests", license: "MIT" },
      2,
      "2026-06-02T00:00:00.000Z",
    );

    insertRecord(db, sourceRecord("xedit.alpha.v1", "alpha", ["xedit", "debugging"]), "test-pack");
    insertRecord(db, sourceRecord("xedit.beta.v1", "beta", ["load-order"]), "test-pack");

    expect(db.prepare("SELECT COUNT(*) AS n FROM records").get()).toEqual({ n: 2 });
    expect(db.prepare("SELECT domain FROM record_domains WHERE record_id = ? ORDER BY domain").all("xedit.alpha.v1")).toEqual([{ domain: "debugging" }, { domain: "xedit" }]);
    expect(db.prepare("SELECT records.id, rank FROM records JOIN records_fts ON records.rowid = records_fts.rowid WHERE records_fts MATCH 'alpha' ORDER BY rank LIMIT 1").all()).toEqual([
      { id: "xedit.alpha.v1", rank: expect.any(Number) },
    ]);
    expect(db.prepare("SELECT rowid, title, query_keys, domains FROM records_fts WHERE records_fts MATCH 'debugging' LIMIT 1").all()).toEqual([
      { rowid: 1, title: "alpha title", query_keys: "alpha", domains: "xedit debugging" },
    ]);
  } finally {
    db.close();
  }
});
