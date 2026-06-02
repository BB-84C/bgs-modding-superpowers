import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { afterEach, expect, test } from "vitest";

import { buildManifest, sha256File, writeManifest } from "../../src/build/manifest.js";
import type { SourceRecord } from "../../src/build/types.js";
import { cleanupTempPacks, makeTempPack } from "./test-helpers.js";

afterEach(cleanupTempPacks);

function record(id: string, domains: string[], games: string[], engineFamilies: string[]): SourceRecord {
  return {
    sourcePath: `records/${id}.md`,
    id,
    title: id,
    domains,
    appliesTo: { games, engineFamilies },
    canonical: { answer: `${id} canonical answer for manifest tests.`, confidence: "verified-project-doc" },
    sources: [{ kind: "project-internal-doc", ref: "tests/unit/manifest.test.ts" }],
    lastReviewed: "2026-06-02",
    schemaVersion: 1,
    bodyMd: "# Body\n",
  };
}

test("buildManifest unions and sorts metadata and writeManifest is deterministic", async () => {
  const packRoot = await makeTempPack("kb-manifest-");
  const sqlitePath = join(packRoot, "kb.sqlite");
  await import("node:fs/promises").then((fs) => fs.writeFile(sqlitePath, "manifest-test"));
  const sha = await sha256File(sqlitePath);
  expect(sha).toMatch(/^[a-f0-9]{64}$/);
  const builtAt = "2026-06-02T00:00:00.000Z";
  expect(Date.parse(builtAt)).not.toBeNaN();

  const manifest = await buildManifest({
    packRoot,
    records: [
      record("xedit.b.v1", ["xedit", "debugging"], ["SkyrimSE", "Fallout4"], ["creation-engine"]),
      record("load-order.a.v1", ["load-order"], ["Fallout3"], ["gamebryo"]),
    ],
    meta: { packId: "test-pack", displayName: "Test Pack", version: "2026.06.02", schemaVersion: 1, minPluginVersion: "0.2.0", owner: "tests", license: "MIT" },
    builtAt,
    sha256: sha,
  });

  expect(manifest.recordCount).toBe(2);
  expect(manifest.domains).toEqual(["debugging", "load-order", "xedit"]);
  expect(manifest.games).toEqual(["Fallout3", "Fallout4", "SkyrimSE"]);
  expect(manifest.engineFamilies).toEqual(["creation-engine", "gamebryo"]);
  expect(manifest.sha256["kb.sqlite"]).toBe(sha);

  const manifestPath = await writeManifest(packRoot, manifest);
  const first = await readFile(manifestPath, "utf8");
  await writeManifest(packRoot, manifest);
  const second = await readFile(manifestPath, "utf8");
  expect(second).toBe(first);
});

test("buildManifest populates sourceCommit when packRoot is inside the git repo", async () => {
  const manifest = await buildManifest({
    packRoot: process.cwd(),
    records: [record("xedit.git.v1", ["xedit"], ["Fallout4"], ["creation-engine"])],
    meta: { packId: "git-pack", displayName: "Git Pack", version: "2026.06.02", schemaVersion: 1, minPluginVersion: "0.2.0", owner: "tests", license: "MIT" },
    builtAt: "2026-06-02T00:00:00.000Z",
    sha256: "a".repeat(64),
  });

  expect(manifest.sourceCommit).toMatch(/^[a-f0-9]{40}$/);
});
