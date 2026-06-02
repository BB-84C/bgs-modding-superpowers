import { existsSync } from "node:fs";
import { afterEach, beforeAll, expect, test } from "vitest";

import { cleanupTempPacks, makeTempPack, recordFrontmatter, runCli, writeRecord } from "./test-helpers.js";

afterEach(cleanupTempPacks);

beforeAll(() => {
  // Spawn-based CLI tests exercise dist/cli.js; run `npm run build` before `npm test`.
  expect(existsSync("dist/cli.js")).toBe(true);
});

test("CLI validate exits 0 on a valid pack", async () => {
  const packRoot = await makeTempPack("kb-cli-validate-ok-");
  await writeRecord(packRoot, "xedit/valid.v1.md", recordFrontmatter({ id: "xedit.valid.v1" }));

  const result = await runCli(["validate", packRoot]);

  expect(result.code).toBe(0);
  expect(result.stdout).toContain("OK: 1 records valid");
  expect(result.stdout).toContain("summary: xedit: 1");
});

test("CLI validate exits 1 and prints source path plus JSON pointer for corrupt records", async () => {
  const packRoot = await makeTempPack("kb-cli-validate-bad-");
  await writeRecord(packRoot, "xedit/bad.v1.md", recordFrontmatter({ id: "xedit.bad.v1", sources: "sources: []" }));

  const result = await runCli(["validate", packRoot]);

  expect(result.code).toBe(1);
  expect(result.combined).toContain("records/xedit/bad.v1.md:/sources: must NOT have fewer than 1 items");
  expect(result.combined).toContain("FAIL: 0 valid, 1 failing");
});
