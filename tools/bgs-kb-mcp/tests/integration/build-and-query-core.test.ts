import { cp, mkdir, readdir, readFile, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterEach, describe, expect, test } from "vitest";

import { buildPack } from "../../src/build/index.js";

const integrationEnabled = process.env.BGS_KB_MCP_INTEGRATION === "1";
const cleanupRoots: string[] = [];

afterEach(async () => {
  for (const root of cleanupRoots.splice(0)) {
    await rm(root, { force: true, recursive: true });
  }
});

const require = createRequire(import.meta.url);
const { DatabaseSync } = require("node:sqlite") as {
  DatabaseSync: new (path: string, options?: { readOnly?: boolean }) => {
    prepare(sql: string): { all(...args: unknown[]): Array<Record<string, unknown>>; get(...args: unknown[]): Record<string, unknown> };
    close(): void;
  };
};

function ftsExpression(query: string): string {
  return query
    .split(/\s+/)
    .filter(Boolean)
    .join(" OR ");
}

async function countMarkdownFiles(root: string): Promise<number> {
  const entries = await readdir(root, { withFileTypes: true });
  const counts = await Promise.all(
    entries.map(async (entry) => {
      const full = join(root, entry.name);
      if (entry.isDirectory()) return countMarkdownFiles(full);
      return entry.isFile() && entry.name.endsWith(".md") ? 1 : 0;
    }),
  );
  return counts.reduce((sum, count) => sum + count, 0);
}

describe.skipIf(!integrationEnabled)("KB-1h core pack build + FTS5 smoke", () => {
  test("builds the real core records and returns expected top-3 FTS5 hits", async () => {
    const repoRoot = resolve("..", "..");
    const coreRecordsRoot = join(repoRoot, "knowledge", "bgs-kb", "packs", "core", "records");
    const expectedRecordCount = await countMarkdownFiles(coreRecordsRoot);
    const packRoot = join(tmpdir(), `kb-integration-${Date.now()}-${Math.random().toString(16).slice(2)}`);
    cleanupRoots.push(packRoot);
    await mkdir(packRoot, { recursive: true });
    await cp(coreRecordsRoot, join(packRoot, "records"), { recursive: true });

    const result = await buildPack(packRoot);

    expect(result.recordCount).toBe(expectedRecordCount);
    expect(existsSync(result.kbSqlitePath)).toBe(true);
    expect(existsSync(result.manifestPath)).toBe(true);
    const manifest = JSON.parse(await readFile(result.manifestPath, "utf8")) as { recordCount: number };
    expect(manifest.recordCount).toBe(expectedRecordCount);

    const db = new DatabaseSync(result.kbSqlitePath, { readOnly: true });
    try {
      const cases = [
        { query: "plugins", expected: "load-order.plugins-txt-modern-asterisk.v1" },
        { query: "OnInit OnLoad", expected: "papyrus.oninit-vs-onload.v1" },
        { query: "loose archive", expected: "archive-precedence.loose-over-archive.v1" },
        { query: "FormID prefix", expected: "xedit.formid-prefix-stripping.v1" },
        { query: "data path", expected: "tooling-mo2.xedit-data-path-flag.v1" },
      ];

      for (const { query, expected } of cases) {
        const rows = db
          .prepare(
            "SELECT records.id, rank FROM records JOIN records_fts ON records.rowid = records_fts.rowid WHERE records_fts MATCH ? ORDER BY rank LIMIT 5",
          )
          .all(ftsExpression(query)) as Array<{ id: string; rank: number }>;
        const topFive = rows.map((row) => row.id);
        expect(rows.length, `query '${query}' returned no hits; top5=${topFive.join(", ")}`).toBeGreaterThan(0);
        expect(topFive.slice(0, 3), `query '${query}' top5=${topFive.join(", ")}`).toContain(expected);
        expect(rows[0].rank, `query '${query}' rank should be BM25 negative`).toBeLessThan(0);
      }
    } finally {
      db.close();
    }
  });
});
