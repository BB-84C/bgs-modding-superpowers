import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname } from "node:path";

import type { PackMeta, SourceRecord } from "./types.js";

const require = createRequire(import.meta.url);
const { DatabaseSync } = require("node:sqlite") as {
  DatabaseSync: new (path: string) => DbHandle;
};

export interface DbHandle {
  exec(sql: string): void;
  prepare(sql: string): { run: (...args: unknown[]) => unknown; get: (...args: unknown[]) => unknown; all: (...args: unknown[]) => unknown };
  close(): void;
}

function jsonOrNull(value: unknown): string | null {
  return value === undefined ? null : JSON.stringify(value);
}

export function openDb(path: string): DbHandle {
  mkdirSync(dirname(path), { recursive: true });
  const db = new DatabaseSync(path);
  db.exec("PRAGMA foreign_keys = ON");
  return db;
}

export function applySchema(db: DbHandle): void {
  db.exec(`
CREATE TABLE records (
  id            TEXT PRIMARY KEY,
  pack_id       TEXT NOT NULL,
  title         TEXT NOT NULL,
  body_md       TEXT NOT NULL,
  canonical_answer TEXT NOT NULL,
  applies_to_json  TEXT NOT NULL,
  variants_json    TEXT,
  query_keys_json  TEXT,
  query_keys    TEXT,
  domains       TEXT,
  severity      TEXT,
  confidence    TEXT NOT NULL,
  sources_json  TEXT NOT NULL,
  related_json  TEXT,
  see_also_json TEXT,
  last_reviewed TEXT NOT NULL,
  schema_version INTEGER NOT NULL
);

CREATE TABLE record_domains (
  record_id TEXT NOT NULL,
  domain    TEXT NOT NULL,
  PRIMARY KEY (record_id, domain)
);

CREATE TABLE record_games (
  record_id  TEXT NOT NULL,
  game       TEXT NOT NULL,
  confidence TEXT,
  PRIMARY KEY (record_id, game)
);

CREATE TABLE record_excludes (
  record_id TEXT NOT NULL,
  game      TEXT NOT NULL,
  reason    TEXT,
  PRIMARY KEY (record_id, game)
);

CREATE TABLE record_engine_families (
  record_id TEXT NOT NULL,
  engine_family TEXT NOT NULL,
  PRIMARY KEY (record_id, engine_family)
);

CREATE TABLE pack_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE VIRTUAL TABLE records_fts USING fts5(
  title,
  body_md,
  query_keys,
  domains,
  content='records',
  content_rowid='rowid',
  tokenize='porter unicode61'
);

CREATE TRIGGER records_ai AFTER INSERT ON records BEGIN
  INSERT INTO records_fts(rowid, title, body_md, query_keys, domains)
  VALUES (
    new.rowid,
    new.title,
    new.body_md,
    coalesce(new.query_keys, ''),
    coalesce(new.domains, '')
  );
END;

CREATE TRIGGER records_ad AFTER DELETE ON records BEGIN
  INSERT INTO records_fts(records_fts, rowid, title, body_md, query_keys, domains)
  VALUES (
    'delete',
    old.rowid,
    old.title,
    old.body_md,
    coalesce(old.query_keys, ''),
    coalesce(old.domains, '')
  );
END;

CREATE TRIGGER records_au AFTER UPDATE ON records BEGIN
  INSERT INTO records_fts(records_fts, rowid, title, body_md, query_keys, domains)
  VALUES (
    'delete',
    old.rowid,
    old.title,
    old.body_md,
    coalesce(old.query_keys, ''),
    coalesce(old.domains, '')
  );
  INSERT INTO records_fts(rowid, title, body_md, query_keys, domains)
  VALUES (
    new.rowid,
    new.title,
    new.body_md,
    coalesce(new.query_keys, ''),
    coalesce(new.domains, '')
  );
END;

CREATE INDEX idx_record_games_game ON record_games(game);
CREATE INDEX idx_record_domains_domain ON record_domains(domain);
CREATE INDEX idx_record_excludes_game ON record_excludes(game);
`);
}

export function insertRecord(db: DbHandle, record: SourceRecord, packId: string): void {
  db.exec("BEGIN");
  try {
    const domainStmt = db.prepare("INSERT INTO record_domains(record_id, domain) VALUES (?, ?)");
    for (const domain of record.domains) domainStmt.run(record.id, domain);

    const gameStmt = db.prepare("INSERT INTO record_games(record_id, game, confidence) VALUES (?, ?, ?)");
    for (const game of record.appliesTo.games) gameStmt.run(record.id, game, null);

    const excludeStmt = db.prepare("INSERT INTO record_excludes(record_id, game, reason) VALUES (?, ?, ?)");
    for (const game of record.appliesTo.excludes ?? []) excludeStmt.run(record.id, game, null);

    const engineStmt = db.prepare("INSERT INTO record_engine_families(record_id, engine_family) VALUES (?, ?)");
    for (const engineFamily of record.appliesTo.engineFamilies ?? []) engineStmt.run(record.id, engineFamily);

    db.prepare(`
INSERT INTO records (
  id, pack_id, title, body_md, canonical_answer, applies_to_json, variants_json,
  query_keys_json, query_keys, domains, severity, confidence, sources_json, related_json, see_also_json,
  last_reviewed, schema_version
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
`).run(
      record.id,
      packId,
      record.title,
      record.bodyMd,
      record.canonical.answer,
      JSON.stringify(record.appliesTo),
      jsonOrNull(record.variants),
      jsonOrNull(record.queryKeys),
      (record.queryKeys ?? []).join(" "),
      record.domains.join(" "),
      record.severity ?? null,
      record.canonical.confidence,
      JSON.stringify(record.sources),
      jsonOrNull(record.related),
      jsonOrNull(record.seeAlso),
      record.lastReviewed,
      record.schemaVersion,
    );
    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}

export function writePackMeta(db: DbHandle, meta: PackMeta, recordCount: number, builtAt: string): void {
  const entries: Record<string, string> = {
    packId: meta.packId,
    displayName: meta.displayName,
    version: meta.version,
    schemaVersion: String(meta.schemaVersion),
    minPluginVersion: meta.minPluginVersion,
    owner: meta.owner,
    license: meta.license,
    recordCount: String(recordCount),
    builtAt,
  };
  const stmt = db.prepare("INSERT INTO pack_meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value");
  for (const [key, value] of Object.entries(entries)) stmt.run(key, value);
}
