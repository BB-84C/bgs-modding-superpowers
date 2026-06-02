import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { afterEach, expect, test } from "vitest";

import { buildPack } from "../../src/build/index.js";
import type { LoadedPack } from "../../src/discovery/types.js";
import { openSessions } from "../../src/session/index.js";
import { makeQueryTool } from "../../src/tools/query.js";
import { cleanupTempPacks, makeTempPack, writeRecord } from "./test-helpers.js";

afterEach(cleanupTempPacks);

const ALL_GAMES = ["SkyrimLE", "SkyrimSE", "SkyrimAE", "SkyrimVR", "Fallout4", "Fallout4VR", "Fallout3", "FalloutNV", "Starfield"];

async function buildLatencyPack(): Promise<LoadedPack> {
  const packRoot = await makeTempPack("kb-query-latency-");
  await writeFile(
    join(packRoot, "bgs-kb-meta.yml"),
    "packId: latency-pack\ndisplayName: Latency Pack\nversion: 2026.06.02\nschemaVersion: 1\nminPluginVersion: 0.2.0\nowner: tests\nlicense: MIT\n",
    "utf8",
  );
  for (let i = 0; i < 100; i += 1) {
    await writeRecord(
      packRoot,
      `load-order/plugins-latency-${i}.v1.md`,
      `---
id: load-order.plugins-latency-${i}.v1
title: Plugins latency ${i}
domains: [load-order]
appliesTo:
  games: [${ALL_GAMES.join(", ")}]
  engineFamilies: [creation-engine]
canonical:
  answer: Plugins latency ${i} canonical answer for query tests.
  confidence: verified-project-doc
queryKeys: [plugins, latency]
sources:
  - kind: project-internal-doc
    ref: tests/unit/tool-query-latency.test.ts
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Plugins latency ${i}

This record mentions plugins several times for retrieval latency testing. Plugins are active markers in this fixture.
`,
    );
  }
  const built = await buildPack(packRoot);
  return {
    packId: built.manifest.packId,
    displayName: built.manifest.displayName,
    version: built.manifest.version,
    schemaVersion: built.manifest.schemaVersion,
    minPluginVersion: built.manifest.minPluginVersion,
    root: "bundled",
    rootPath: packRoot,
    packRoot,
    kbSqlitePath: built.kbSqlitePath,
    manifestPath: built.manifestPath,
    manifest: built.manifest,
    integrityOk: true,
    loadedAt: "2026-06-02T00:00:00.000Z",
  };
}

test("query latency smoke stays under the KB-2 budget on 100 records", async () => {
  const pack = await buildLatencyPack();
  const registry = openSessions([pack]);
  try {
    const tool = makeQueryTool({ registry });
    const elapsed: number[] = [];
    for (let i = 0; i < 10; i += 1) {
      const env = await tool({ query: "plugins", maxResults: 5 });
      if (!env.ok) throw new Error(`expected ok envelope, got ${env.code}`);
      elapsed.push(env.data.stats.elapsedMs);
    }
    const sorted = [...elapsed].sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length / 2)];
    const max = sorted.at(-1) ?? 0;

    // Smoke budget: median should satisfy the KB-2 p95 target class on normal
    // developer hardware; max is intentionally loose to avoid CI noise.
    expect(median).toBeLessThan(50);
    expect(max).toBeLessThan(200);
  } finally {
    registry.closeAll();
  }
});
