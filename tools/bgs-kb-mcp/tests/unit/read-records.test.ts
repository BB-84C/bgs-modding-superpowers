import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { afterEach, expect, test } from "vitest";

import { readRecords } from "../../src/build/read-records.js";
import { cleanupTempPacks, makeTempPack, recordFrontmatter, writeRecord } from "./test-helpers.js";

afterEach(cleanupTempPacks);

test("readRecords discovers nested records, skips root README.md and draft records, and emits stable sourcePath", async () => {
  const packRoot = await makeTempPack("kb-read-records-");
  await mkdir(join(packRoot, "records"), { recursive: true });
  await writeFile(join(packRoot, "records", "README.md"), "# Not a record\n", "utf8");
  await writeRecord(packRoot, "xedit/visible-record.v1.md", recordFrontmatter({ id: "xedit.visible-record.v1", title: "Visible record" }));
  await writeRecord(
    packRoot,
    "xedit/draft-record.v1.md",
    recordFrontmatter({ id: "xedit.draft-record.v1", title: "Draft record" }).replace("schemaVersion: 1", "schemaVersion: 1\n_draft: true"),
  );

  const records = await readRecords(packRoot);

  expect(records.map((record) => record.id)).toEqual(["xedit.visible-record.v1"]);
  expect(records[0].sourcePath).toBe("records/xedit/visible-record.v1.md");
  expect(records[0].sourcePath).not.toContain("\\");
});

test("readRecords reports malformed YAML with the relative source path", async () => {
  const packRoot = await makeTempPack("kb-read-records-bad-yaml-");
  await writeRecord(packRoot, "xedit/bad-yaml.v1.md", "---\nid: [unterminated\n---\n\n# Bad\n");

  await expect(readRecords(packRoot)).rejects.toThrow(/records\/xedit\/bad-yaml\.v1\.md/);
});
