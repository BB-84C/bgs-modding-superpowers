import { existsSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { afterEach, expect, test } from "vitest";
import { extractZip } from "../../src/tools/install/extract.js";
import { cleanupTempPacks, makeTempPack } from "./test-helpers.js";
import { makeZip } from "./zip-fixture.js";

afterEach(cleanupTempPacks);

test.each(["../extract-sibling/escaped.txt", "..\\extract-sibling\\escaped.txt"])("real ZIP rejects prefix-sibling escape %s before writing", async (entry) => {
  const root = await makeTempPack("kb-zip-safety-");
  const archive = join(root, "malicious.zip");
  await writeFile(archive, makeZip({ [entry]: "must not escape" }));
  // A raw startsWith(destRoot) guard alone would allow this sibling. yauzl's
  // filename validation must reject it on the actual extraction path.
  await expect(extractZip(archive, join(root, "extract"))).rejects.toThrow("invalid relative path");
  expect(existsSync(join(root, "extract-sibling"))).toBe(false);
});
