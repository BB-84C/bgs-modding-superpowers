import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, expect, test } from "vitest";

import { buildPack } from "../../src/build/index.js";

const createdRoots: string[] = [];

afterEach(async () => {
  for (const root of createdRoots.splice(0)) {
    await rm(root, { force: true, recursive: true });
  }
});

test("buildPack writes a SQLite pack and manifest from source records", async () => {
  const testDir = dirname(fileURLToPath(import.meta.url));
  const packRoot = join(testDir, ".test-pack-build");
  createdRoots.push(packRoot);
  await rm(packRoot, { force: true, recursive: true });
  await mkdir(join(packRoot, "records", "xedit"), { recursive: true });
  await writeFile(
    join(packRoot, "records", "xedit", "plugins-query.v1.md"),
    `---
id: xedit.plugins-query.v1
title: Plugins query smoke record
domains: [xedit]
appliesTo:
  games: [Fallout4]
  engineFamilies: [creation-engine]
canonical:
  answer: Plugins query smoke record for FTS5 build verification.
  confidence: verified-project-doc
queryKeys: [plugins, load order]
severity: low
sources:
  - kind: project-internal-doc
    ref: tests/unit/build-pack.test.ts
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Plugins query smoke record

This body mentions plugins and load order so the FTS index can find it.
`,
    "utf8",
  );

  const result = await buildPack(packRoot);

  expect(result.recordCount).toBe(1);
  expect(result.sha256).toMatch(/^[a-f0-9]{64}$/);

  const manifest = JSON.parse(await readFile(result.manifestPath, "utf8")) as { recordCount: number; sha256: { "kb.sqlite": string } };
  expect(manifest.recordCount).toBe(1);
  expect(manifest.sha256["kb.sqlite"]).toBe(result.sha256);

  // Vite's builtin-module list may lag new Node builtins, so keep this dynamic
  // and ignored by the transformer while still exercising real node:sqlite.
  const require = createRequire(import.meta.url);
  const { DatabaseSync } = require("node:sqlite") as { DatabaseSync: new (path: string) => { prepare: (sql: string) => { get: () => unknown; all: () => unknown[] }; close: () => void } };
  const db = new DatabaseSync(result.kbSqlitePath);
  try {
    expect(db.prepare("SELECT COUNT(*) AS n FROM records").get()).toEqual({ n: 1 });
    expect(db.prepare("SELECT value FROM pack_meta WHERE key = 'recordCount'").get()).toEqual({ value: "1" });
    const hits = db
      .prepare("SELECT records.id FROM records JOIN records_fts ON records.rowid = records_fts.rowid WHERE records_fts MATCH 'plugins'")
      .all();
    expect(hits).toEqual([{ id: "xedit.plugins-query.v1" }]);
  } finally {
    db.close();
  }
});
