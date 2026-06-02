import { mkdir, rm, unlink, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, expect, test } from "vitest";

import { buildPack } from "../../src/build/index.js";
import { formatInfo } from "../../src/info/format.js";
import { gatherInfo } from "../../src/info/index.js";

const createdRoots: string[] = [];

afterEach(async () => {
  for (const root of createdRoots.splice(0)) {
    await rm(root, { force: true, recursive: true });
  }
});

async function createPack(packRoot: string): Promise<void> {
  await mkdir(join(packRoot, "records", "xedit"), { recursive: true });
  await writeFile(
    join(packRoot, "records", "xedit", "info-record.v1.md"),
    `---
id: xedit.info-record.v1
title: Info record
domains: [xedit, debugging]
appliesTo:
  games: [Fallout4, SkyrimSE]
  engineFamilies: [creation-engine]
canonical:
  answer: Info record canonical answer for tests.
  confidence: verified-project-doc
sources:
  - kind: project-internal-doc
    ref: tests/unit/info.test.ts
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Info record

Info body.
`,
    "utf8",
  );
}

test("gatherInfo reconciles manifest and SQLite counts", async () => {
  const testDir = dirname(fileURLToPath(import.meta.url));
  const packRoot = join(testDir, ".test-pack-info-built");
  createdRoots.push(packRoot);
  await rm(packRoot, { force: true, recursive: true });
  await createPack(packRoot);
  await buildPack(packRoot);

  const info = await gatherInfo(packRoot);
  const formatted = formatInfo(info);

  expect(info.manifest?.recordCount).toBe(1);
  expect(info.sqlite?.recordCount).toBe(1);
  expect(info.sqlite?.sha256Verified).toBe(true);
  expect(info.byDomain).toEqual({ debugging: 1, xedit: 1 });
  expect(formatted).toContain("Records:        1 (manifest) / 1 (kb.sqlite)");
  expect(formatted).toContain("sha256 verified: yes");
});

test("gatherInfo warns and derives record data when manifest is missing", async () => {
  const testDir = dirname(fileURLToPath(import.meta.url));
  const packRoot = join(testDir, ".test-pack-info-missing-manifest");
  createdRoots.push(packRoot);
  await rm(packRoot, { force: true, recursive: true });
  await createPack(packRoot);
  await buildPack(packRoot);
  await unlink(join(packRoot, "manifest.json"));

  const info = await gatherInfo(packRoot);
  const formatted = formatInfo(info);

  expect(info.warnings).toContain("manifest.json missing; pack has not been built yet. Run `bgs-kb-mcp build <pack-root>`.");
  expect(info.derivedRecordCount).toBe(1);
  expect(formatted).toContain("WARN: manifest.json missing");
  expect(formatted).toContain("Records:        1 (records/) / 1 (kb.sqlite)");
});
