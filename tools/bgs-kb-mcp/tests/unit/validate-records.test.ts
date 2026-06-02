import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, expect, test } from "vitest";

import { readRecords } from "../../src/build/read-records.js";
import { formatValidationError, validateRecords } from "../../src/build/validate.js";

const createdRoots: string[] = [];

afterEach(async () => {
  for (const root of createdRoots.splice(0)) {
    await rm(root, { force: true, recursive: true });
  }
});

async function writeRecord(packRoot: string, relativePath: string, frontmatter: string): Promise<void> {
  const recordPath = join(packRoot, "records", ...relativePath.split("/"));
  await mkdir(dirname(recordPath), { recursive: true });
  await writeFile(recordPath, `${frontmatter}
---

# Test record

Body content for validation.
`, "utf8");
}

const validFrontmatter = `---
id: xedit.valid-record.v1
title: Valid record
domains: [xedit]
appliesTo:
  games: [Fallout4]
canonical:
  answer: Valid record canonical answer for tests.
  confidence: verified-project-doc
sources:
  - kind: project-internal-doc
    ref: tests/unit/validate-records.test.ts
lastReviewed: "2026-06-02"
schemaVersion: 1`;

test("validateRecords returns valid records plus formatted schema errors", async () => {
  const testDir = dirname(fileURLToPath(import.meta.url));
  const packRoot = join(testDir, ".test-pack-validate");
  createdRoots.push(packRoot);
  await rm(packRoot, { force: true, recursive: true });
  await writeRecord(packRoot, "xedit/valid-record.v1.md", validFrontmatter);
  await writeRecord(
    packRoot,
    "xedit/broken-record.v1.md",
    validFrontmatter.replace("id: xedit.valid-record.v1", "id: xedit.broken-record.v1").replace(/sources:\n  - kind: project-internal-doc\n    ref: tests\/unit\/validate-records.test.ts/, "sources: []"),
  );

  const records = await readRecords(packRoot);
  const result = validateRecords(records, packRoot);

  expect(result.valid.map((record) => record.id)).toEqual(["xedit.valid-record.v1"]);
  expect(result.errors).toHaveLength(1);
  expect(formatValidationError(result.errors[0].sourcePath, result.errors[0].errors[0])).toContain("records/xedit/broken-record.v1.md:/sources:");
});

test("validateRecords resolves the project schema for a pack copied outside the repo", async () => {
  const packRoot = await mkdtemp(join(tmpdir(), "kb-validate-outside-repo-"));
  createdRoots.push(packRoot);
  await writeRecord(packRoot, "xedit/valid-record.v1.md", validFrontmatter);

  const records = await readRecords(packRoot);
  const result = validateRecords(records, packRoot);

  expect(result.errors).toEqual([]);
  expect(result.valid).toHaveLength(1);
});
