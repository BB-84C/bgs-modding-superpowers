import { afterEach, expect, test } from "vitest";

import { validateRecords } from "../../src/build/validate.js";
import type { SourceRecord } from "../../src/build/types.js";
import { cleanupTempPacks, makeTempPack } from "./test-helpers.js";

afterEach(cleanupTempPacks);

function sourceRecord(overrides: Partial<SourceRecord> & { id: string; sourcePath: string }): SourceRecord {
  return {
    title: overrides.id,
    domains: ["xedit"],
    appliesTo: { games: ["Fallout4"], engineFamilies: ["creation-engine"] },
    canonical: { answer: `${overrides.id} canonical answer for tests.`, confidence: "verified-project-doc" },
    sources: [{ kind: "project-internal-doc", ref: "tests/unit/build-validate-edge-cases.test.ts" }],
    lastReviewed: "2026-06-02",
    schemaVersion: 1,
    bodyMd: "# Body\n",
    ...overrides,
  };
}

test("validateRecords returns all records when a ten-record set is valid", async () => {
  const packRoot = await makeTempPack("kb-validate-valid-");
  const records = Array.from({ length: 10 }, (_, i) => {
    const id = `xedit.valid-${i}.v1`;
    return sourceRecord({ id, sourcePath: `records/xedit/valid-${i}.v1.md` });
  });

  const result = validateRecords(records, packRoot);

  expect(result.valid).toHaveLength(10);
  expect(result.errors).toEqual([]);
});

test("validateRecords flags duplicate ids on both source paths", async () => {
  const packRoot = await makeTempPack("kb-validate-duplicate-");
  const records = [
    sourceRecord({ id: "xedit.duplicate.v1", sourcePath: "records/xedit/duplicate.v1.md" }),
    sourceRecord({ id: "xedit.duplicate.v1", sourcePath: "records/xedit/other.v1.md" }),
  ];

  const result = validateRecords(records, packRoot);

  expect(result.errors.map((error) => error.sourcePath)).toEqual(["records/xedit/other.v1.md", "records/xedit/duplicate.v1.md", "records/xedit/other.v1.md"]);
  expect(result.errors.flatMap((error) => error.errors.map((inner) => inner.message))).toContain("duplicate id 'xedit.duplicate.v1' also appears in records/xedit/duplicate.v1.md, records/xedit/other.v1.md");
});

test.each([
  {
    name: "games and excludes overlap",
    record: sourceRecord({ id: "xedit.overlap.v1", sourcePath: "records/xedit/overlap.v1.md", appliesTo: { games: ["Fallout4"], excludes: ["Fallout4"] } }),
    message: "must not overlap appliesTo.games (Fallout4)",
  },
  {
    name: "empty sources array",
    record: sourceRecord({ id: "xedit.empty-sources.v1", sourcePath: "records/xedit/empty-sources.v1.md", sources: [] }),
    message: "must NOT have fewer than 1 items",
  },
  {
    name: "id mismatches filename stem",
    record: sourceRecord({ id: "xedit.wrong-id.v1", sourcePath: "records/xedit/expected-id.v1.md" }),
    message: "must match source path stem 'xedit.expected-id.v1'",
  },
])("validateRecords flags $name", async ({ record, message }) => {
  const packRoot = await makeTempPack("kb-validate-edge-");

  const result = validateRecords([record], packRoot);

  expect(result.errors.flatMap((error) => error.errors.map((inner) => inner.message))).toContain(message);
});
