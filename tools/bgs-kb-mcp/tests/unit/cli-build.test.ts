import { existsSync, statSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { afterEach, beforeAll, expect, test } from "vitest";

import { cleanupTempPacks, makeTempPack, runCli, writeFixturePack } from "./test-helpers.js";

afterEach(cleanupTempPacks);

beforeAll(() => {
  // Spawn-based CLI tests exercise dist/cli.js; run `npm run build` before `npm test`.
  expect(existsSync("dist/cli.js")).toBe(true);
});

test("CLI build exits 0, prints a summary, and writes kb.sqlite plus manifest.json", async () => {
  const packRoot = await makeTempPack("kb-cli-build-");
  await writeFixturePack(packRoot, [
    { path: "xedit/alpha.v1.md", id: "xedit.alpha.v1", queryKeys: ["alpha"] },
    { path: "load-order/beta.v1.md", id: "load-order.beta.v1", domains: ["load-order"], queryKeys: ["beta"] },
  ]);

  const result = await runCli(["build", packRoot]);

  expect(result.code).toBe(0);
  expect(result.stdout).toContain("records:  2");
  expect(result.stdout).toMatch(/sha256 [a-f0-9]{64}/);
  const sqlitePath = join(packRoot, "kb.sqlite");
  expect(existsSync(sqlitePath)).toBe(true);
  expect(statSync(sqlitePath).size).toBeGreaterThan(0);
  const manifest = JSON.parse(await readFile(join(packRoot, "manifest.json"), "utf8")) as { recordCount: number; sha256: { "kb.sqlite": string }; packId: string };
  expect(manifest.recordCount).toBe(2);
  expect(manifest.sha256["kb.sqlite"]).toMatch(/^[a-f0-9]{64}$/);
  expect(manifest.packId).toBe(packRoot.split(/[\\/]/).at(-1));
});
