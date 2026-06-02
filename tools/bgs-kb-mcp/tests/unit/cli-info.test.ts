import { existsSync } from "node:fs";
import { rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { afterEach, beforeAll, expect, test } from "vitest";

import { buildPack } from "../../src/build/index.js";
import { cleanupTempPacks, makeTempPack, runCli, writeFixturePack } from "./test-helpers.js";

afterEach(cleanupTempPacks);

beforeAll(() => {
  // Spawn-based CLI tests exercise dist/cli.js; run `npm run build` before `npm test`.
  expect(existsSync("dist/cli.js")).toBe(true);
});

async function builtPack(): Promise<string> {
  const packRoot = await makeTempPack("kb-cli-info-");
  await writeFixturePack(packRoot, [
    { path: "xedit/alpha.v1.md", id: "xedit.alpha.v1", queryKeys: ["alpha"] },
    { path: "load-order/beta.v1.md", id: "load-order.beta.v1", domains: ["load-order"], queryKeys: ["beta"] },
  ]);
  await buildPack(packRoot);
  return packRoot;
}

test("CLI info prints all documented sections for a built pack", async () => {
  const packRoot = await builtPack();

  const result = await runCli(["info", packRoot]);

  expect(result.code).toBe(0);
  for (const section of ["Pack:", "Display name:", "Version:", "Records:", "Domains:", "Games:", "Engine fams:", "kb.sqlite:", "manifest.json:", "By domain:", "By game (a record may apply to multiple games):"]) {
    expect(result.stdout).toContain(section);
  }
  expect(result.stdout).toContain("sha256 verified: yes");
});

test("CLI info warns and exits 0 when manifest is missing", async () => {
  const packRoot = await builtPack();
  await rm(join(packRoot, "manifest.json"));

  const result = await runCli(["info", packRoot]);

  expect(result.code).toBe(0);
  expect(result.stdout).toContain("WARN: manifest.json missing");
});

test("CLI info warns and exits 0 when kb.sqlite is missing", async () => {
  const packRoot = await builtPack();
  await rm(join(packRoot, "kb.sqlite"));

  const result = await runCli(["info", packRoot]);

  expect(result.code).toBe(0);
  expect(result.stdout).toContain("WARN: kb.sqlite missing; counts from manifest only.");
});

test("CLI info exits 2 when kb.sqlite is corrupt", async () => {
  const packRoot = await builtPack();
  await writeFile(join(packRoot, "kb.sqlite"), "");

  const result = await runCli(["info", packRoot]);

  expect(result.code).toBe(2);
  expect(result.combined).toContain("ERROR:");
});
