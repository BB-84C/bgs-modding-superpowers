import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { afterEach, expect, test } from "vitest";

import { buildPack } from "../../src/build/index.js";
import type { LoadedPack, PackRoot } from "../../src/discovery/types.js";
import { openSessions } from "../../src/session/index.js";
import type { SessionRegistry } from "../../src/session/types.js";
import { makeQueryTool } from "../../src/tools/query.js";
import { cleanupTempPacks, makeTempPack, writeRecord } from "./test-helpers.js";

afterEach(cleanupTempPacks);

const loadedAt = "2026-06-02T00:00:00.000Z";
const ALL_GAMES = ["SkyrimLE", "SkyrimSE", "SkyrimAE", "SkyrimVR", "Fallout4", "Fallout4VR", "Fallout3", "FalloutNV", "Starfield"];

interface FixtureRecord {
  id: string;
  title: string;
  domains: string[];
  games: string[];
  excludes?: string[];
  queryKeys?: string[];
  body: string;
  variantsYaml?: string;
}

function recordMarkdown(record: FixtureRecord): string {
  return `---
id: ${record.id}
title: ${record.title}
domains: [${record.domains.join(", ")}]
appliesTo:
  games: [${record.games.join(", ")}]
  engineFamilies: [creation-engine]
${record.excludes ? `  excludes: [${record.excludes.join(", ")}]\n` : ""}canonical:
  answer: ${record.title} canonical answer for query tests.
  confidence: verified-project-doc
${record.variantsYaml ?? ""}${record.queryKeys ? `queryKeys: [${record.queryKeys.join(", ")}]\n` : ""}sources:
  - kind: project-internal-doc
    ref: tests/unit/tool-query.test.ts
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# ${record.title}

${record.body}
`;
}

async function buildLoadedPack(packId: string, records: FixtureRecord[], root: PackRoot = "bundled"): Promise<LoadedPack> {
  const packRoot = await makeTempPack(`kb-query-${packId}-`);
  await writeFile(
    join(packRoot, "bgs-kb-meta.yml"),
    `packId: ${packId}\ndisplayName: ${packId} display\nversion: 2026.06.02\nschemaVersion: 1\nminPluginVersion: 0.2.0\nowner: tests\nlicense: MIT\n`,
    "utf8",
  );
  for (const record of records) await writeRecord(packRoot, `${record.id.split(".").slice(0, -1).join("/")}.v1.md`, recordMarkdown(record));
  const built = await buildPack(packRoot);
  return {
    packId: built.manifest.packId,
    displayName: built.manifest.displayName,
    version: built.manifest.version,
    schemaVersion: built.manifest.schemaVersion,
    minPluginVersion: built.manifest.minPluginVersion,
    root,
    rootPath: packRoot,
    packRoot,
    kbSqlitePath: built.kbSqlitePath,
    manifestPath: built.manifestPath,
    manifest: built.manifest,
    integrityOk: true,
    loadedAt,
  };
}

function baseRecords(): FixtureRecord[] {
  return [
    {
      id: "xedit.formid-prefix.v1",
      title: "FormID prefix handling",
      domains: ["xedit"],
      games: ALL_GAMES,
      queryKeys: ["FormID prefix"],
      body: "FormID prefix normalization lets callers use FormID values safely across tools.",
    },
    {
      id: "load-order.plugins-modern.v1",
      title: "Modern plugins asterisk",
      domains: ["load-order"],
      games: ["SkyrimSE", "SkyrimAE", "Fallout4", "Starfield"],
      excludes: ["Fallout3", "FalloutNV"],
      queryKeys: ["plugins asterisk"],
      variantsYaml: `variants:
  Fallout4:
    additions:
      - Fallout 4 plugins use the modern active-marker convention.
    warnings:
      - code: FO4_PLUGIN
        severity: high
        text: Confirm plugins.txt before blaming load order.
`,
      body: "Modern plugins asterisk records explain active plugin markers for current games.",
    },
    {
      id: "load-order.plugins-legacy.v1",
      title: "Legacy plugins list",
      domains: ["load-order"],
      games: ["Fallout3", "FalloutNV", "SkyrimLE"],
      queryKeys: ["legacy plugins"],
      body: "Legacy plugins behavior differs for old engines and classic load-order files.",
    },
    {
      id: "papyrus.oninit-onload.v1",
      title: "OnInit OnLoad lifecycle",
      domains: ["papyrus"],
      games: ["Fallout4", "SkyrimSE", "Starfield"],
      excludes: ["Fallout3", "FalloutNV"],
      queryKeys: ["OnInit OnLoad"],
      body: "Papyrus OnInit OnLoad timing differs from plugin loading and save reload behavior.",
    },
    {
      id: "archive-precedence.loose-archive.v1",
      title: "Loose archive precedence",
      domains: ["archive-precedence"],
      games: ALL_GAMES,
      queryKeys: ["loose archive"],
      body: "Loose archive precedence explains how loose files and archives interact.",
    },
  ];
}

async function withQueryTool<T>(packs: LoadedPack[], fn: (tool: ReturnType<typeof makeQueryTool>, registry: SessionRegistry) => Promise<T>, maxResultsCap?: number): Promise<T> {
  const registry = openSessions(packs);
  try {
    return await fn(makeQueryTool({ registry, ...(maxResultsCap ? { maxResultsCap } : {}) }), registry);
  } finally {
    registry.closeAll();
  }
}

test("query returns ranked hits with snippets for a simple query", async () => {
  const pack = await buildLoadedPack("query-pack", baseRecords());
  await withQueryTool([pack], async (tool) => {
    const env = await tool({ query: "plugins" });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data.hits.map((hit) => hit.id)).toEqual(expect.arrayContaining(["load-order.plugins-modern.v1", "load-order.plugins-legacy.v1"]));
    expect(env.data.hits[0].score).toBeGreaterThan(0);
    expect(env.data.hits[0].snippet).toMatch(/\[plugin/i);
  });
});

test("game filter returns modern plugins record for Fallout4 and suppresses legacy", async () => {
  const pack = await buildLoadedPack("query-pack", baseRecords());
  await withQueryTool([pack], async (tool) => {
    const env = await tool({ query: "plugins", games: ["Fallout4"] });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data.hits.map((hit) => hit.id)).toContain("load-order.plugins-modern.v1");
    expect(env.data.hits.map((hit) => hit.id)).not.toContain("load-order.plugins-legacy.v1");
  });
});

test("game filter returns legacy plugins record for FalloutNV and honors excludes", async () => {
  const pack = await buildLoadedPack("query-pack", baseRecords());
  await withQueryTool([pack], async (tool) => {
    const env = await tool({ query: "plugins", games: ["FalloutNV"] });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data.hits.map((hit) => hit.id)).toContain("load-order.plugins-legacy.v1");
    expect(env.data.hits.map((hit) => hit.id)).not.toContain("load-order.plugins-modern.v1");
  });
});

test("excludes suppress otherwise matching records", async () => {
  const pack = await buildLoadedPack("query-pack", baseRecords());
  await withQueryTool([pack], async (tool) => {
    const env = await tool({ query: "OnInit", games: ["FalloutNV"] });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data.hits).toEqual([]);
  });
});

test("domain filter narrows results", async () => {
  const pack = await buildLoadedPack("query-pack", baseRecords());
  await withQueryTool([pack], async (tool) => {
    const xedit = await tool({ query: "FormID", domains: ["xedit"] });
    const papyrus = await tool({ query: "FormID", domains: ["papyrus"] });

    expect(xedit.ok && xedit.data.hits.map((hit) => hit.id)).toEqual(["xedit.formid-prefix.v1"]);
    expect(papyrus.ok && papyrus.data.hits).toEqual([]);
  });
});

test("maxResults is respected and clamped to the configured cap", async () => {
  const many = Array.from({ length: 10 }, (_, i) => ({
    id: `load-order.plugins-${i}.v1`,
    title: `Plugins ${i}`,
    domains: ["load-order"],
    games: ALL_GAMES,
    body: `plugins repeated fixture ${i}`,
  }));
  const pack = await buildLoadedPack("many-pack", many);
  await withQueryTool(
    [pack],
    async (tool) => {
      const requested = await tool({ query: "plugins", maxResults: 3 });
      const clamped = await tool({ query: "plugins", maxResults: 100 });

      expect(requested.ok && requested.data.hits).toHaveLength(3);
      expect(clamped.ok && clamped.data.hits).toHaveLength(3);
    },
    3,
  );
});

test("summary and expanded detail levels shape bodyExcerpt", async () => {
  const pack = await buildLoadedPack("query-pack", baseRecords());
  await withQueryTool([pack], async (tool) => {
    const summary = await tool({ query: "plugins", detailLevel: "summary" });
    const expanded = await tool({ query: "plugins", detailLevel: "expanded" });

    expect(summary.ok && summary.data.hits[0]).not.toHaveProperty("bodyExcerpt");
    expect(expanded.ok && expanded.data.hits[0].bodyExcerpt).toEqual(expect.any(String));
    expect(expanded.ok && expanded.data.hits[0].bodyExcerpt!.length).toBeLessThanOrEqual(500);
  });
});

test("includeSources and includeVariants options omit optional fields", async () => {
  const pack = await buildLoadedPack("query-pack", baseRecords());
  await withQueryTool([pack], async (tool) => {
    const withoutSources = await tool({ query: "plugins", includeSources: false });
    const withoutVariants = await tool({ query: "plugins", games: ["Fallout4"], includeVariants: false });

    expect(withoutSources.ok && withoutSources.data.hits[0]).not.toHaveProperty("sources");
    expect(withoutVariants.ok && withoutVariants.data.hits[0]).not.toHaveProperty("variantNotes");
  });
});

test("variant notes are included for requested games", async () => {
  const pack = await buildLoadedPack("query-pack", baseRecords());
  await withQueryTool([pack], async (tool) => {
    const env = await tool({ query: "plugins", games: ["Fallout4"] });

    expect(env.ok && env.data.hits.find((hit) => hit.id === "load-order.plugins-modern.v1")?.variantNotes).toEqual([
      { game: "Fallout4", text: "Fallout 4 plugins use the modern active-marker convention. [FO4_PLUGIN|high] Confirm plugins.txt before blaming load order." },
    ]);
  });
});

test("packIds filters fan-out to matching packs", async () => {
  const x = await buildLoadedPack("pack-x", [{ id: "load-order.pack-x.v1", title: "Pack X plugins", domains: ["load-order"], games: ALL_GAMES, body: "plugins from pack x" }]);
  const y = await buildLoadedPack("pack-y", [{ id: "load-order.pack-y.v1", title: "Pack Y plugins", domains: ["load-order"], games: ALL_GAMES, body: "plugins from pack y" }], "user");
  await withQueryTool([x, y], async (tool) => {
    const env = await tool({ query: "plugins", packIds: ["pack-x"] });

    expect(env.ok && env.data.hits.map((hit) => hit.packId)).toEqual(["pack-x"]);
  });
});

test("empty results return an ok envelope with zero candidates", async () => {
  const pack = await buildLoadedPack("query-pack", baseRecords());
  await withQueryTool([pack], async (tool) => {
    const env = await tool({ query: "nonexistentterm123abc" });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data.hits).toEqual([]);
    expect(env.data.stats.totalCandidates).toBe(0);
  });
});

test("empty query is invalid_request", async () => {
  const pack = await buildLoadedPack("query-pack", baseRecords());
  await withQueryTool([pack], async (tool) => {
    const env = await tool({ query: "" });

    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
  });
});

test("empty registry refuses with not_loaded", async () => {
  const registry: SessionRegistry = { size: 0, byPackId: () => null, all: () => [], forEach: () => undefined, closeAll: () => undefined };
  const env = await makeQueryTool({ registry })({ query: "plugins" });

  expect(env.ok).toBe(false);
  if (env.ok) throw new Error("expected refusal");
  expect(env.code).toBe("not_loaded");
});

test("cross-pack scores are normalized and sorted monotonically", async () => {
  const x = await buildLoadedPack("pack-x", [{ id: "load-order.pack-x.v1", title: "Pack X plugins", domains: ["load-order"], games: ALL_GAMES, body: "plugins plugins plugins from pack x" }]);
  const y = await buildLoadedPack("pack-y", [{ id: "load-order.pack-y.v1", title: "Pack Y plugins", domains: ["load-order"], games: ALL_GAMES, body: "plugins from pack y" }], "user");
  await withQueryTool([x, y], async (tool) => {
    const env = await tool({ query: "plugins", maxResults: 10 });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data.hits).toHaveLength(2);
    expect(env.data.hits[0].score).toBeGreaterThanOrEqual(env.data.hits[1].score);
  });
});

test("stats include elapsedMs and kbVersionMap", async () => {
  const x = await buildLoadedPack("pack-x", [{ id: "load-order.pack-x.v1", title: "Pack X plugins", domains: ["load-order"], games: ALL_GAMES, body: "plugins from pack x" }]);
  const y = await buildLoadedPack("pack-y", [{ id: "load-order.pack-y.v1", title: "Pack Y plugins", domains: ["load-order"], games: ALL_GAMES, body: "plugins from pack y" }], "user");
  await withQueryTool([x, y], async (tool) => {
    const env = await tool({ query: "plugins" });

    expect(env.ok && env.data.stats.elapsedMs).toEqual(expect.any(Number));
    expect(env.ok && env.data.stats.kbVersionMap).toEqual({ "pack-x": "2026.06.02", "pack-y": "2026.06.02" });
  });
});

test("ties are ordered by packId then id", async () => {
  const b = await buildLoadedPack("pack-b", [{ id: "load-order.same-b.v1", title: "Same B", domains: ["load-order"], games: ALL_GAMES, body: "plugins identical body" }]);
  const a = await buildLoadedPack("pack-a", [{ id: "load-order.same-a.v1", title: "Same A", domains: ["load-order"], games: ALL_GAMES, body: "plugins identical body" }], "user");
  await withQueryTool([b, a], async (tool) => {
    const env = await tool({ query: "plugins", maxResults: 10 });

    expect(env.ok && env.data.hits.map((hit) => `${hit.packId}:${hit.id}`)).toEqual(["pack-a:load-order.same-a.v1", "pack-b:load-order.same-b.v1"]);
  });
});
