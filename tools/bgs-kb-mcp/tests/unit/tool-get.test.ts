import { writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { join } from "node:path";
import { afterEach, expect, test } from "vitest";

// node:sqlite is an experimental Node builtin; TS/Vitest can't statically
// resolve it, so we createRequire it the same way scripts/rebuild-locked-pack.mjs does.
const requireFromHere = createRequire(import.meta.url);
const { DatabaseSync } = requireFromHere("node:sqlite") as typeof import("node:sqlite");

import { buildPack } from "../../src/build/index.js";
import type { LoadedPack, PackRoot } from "../../src/discovery/types.js";
import { openSessions } from "../../src/session/index.js";
import type { SessionRegistry } from "../../src/session/types.js";
import { makeGetTool } from "../../src/tools/get.js";
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
  body: string;
  queryKeys?: string[];
  variantsYaml?: string;
  related?: string[];
  seeAlso?: string[];
}

function recordPath(id: string): string {
  const parts = id.split(".");
  const version = parts.pop();
  return `${parts.join("/")}.${version}.md`;
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
  answer: ${record.title} canonical answer for get tests.
  confidence: verified-project-doc
${record.variantsYaml ?? ""}${record.queryKeys ? `queryKeys: [${record.queryKeys.join(", ")}]\n` : ""}${record.related ? `related: [${record.related.join(", ")}]\n` : ""}${record.seeAlso ? `seeAlso: [${record.seeAlso.join(", ")}]\n` : ""}sources:
  - kind: project-internal-doc
    ref: tests/unit/tool-get.test.ts
    sectionPath: fixture
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# ${record.title}

${record.body}
`;
}

async function buildLoadedPack(packId: string, records: FixtureRecord[], root: PackRoot = "bundled"): Promise<LoadedPack> {
  const packRoot = await makeTempPack(`kb-get-${packId}-`);
  await writeFile(
    join(packRoot, "bgs-kb-meta.yml"),
    `packId: ${packId}\ndisplayName: ${packId} display\nversion: 2026.06.02\nschemaVersion: 1\nminPluginVersion: 0.2.0\nowner: tests\nlicense: MIT\n`,
    "utf8",
  );
  for (const record of records) await writeRecord(packRoot, recordPath(record.id), recordMarkdown(record));
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
      id: "archive-precedence.loose-over-archive.v1",
      title: "Loose files override archives",
      domains: ["archive-precedence"],
      games: ALL_GAMES,
      queryKeys: ["loose archive"],
      body: "Loose files usually win over archived assets in the base explanation.",
      variantsYaml: `variants:
  Fallout4:
    additions:
      - BA2 packaging and precombine/previs can affect the visible result.
    warnings:
      - code: PREVIS
        severity: high
        text: Check precombine/previs before blaming plugin load order.
`,
    },
    {
      id: "papyrus.oninit-vs-onload.v1",
      title: "OnInit is not OnLoad",
      domains: ["papyrus"],
      games: ["Fallout4", "SkyrimSE", "Starfield"],
      excludes: ["Fallout3", "FalloutNV"],
      body: "Papyrus OnInit is not a universal load callback.",
    },
    {
      id: "load-order.plugins-modern.v1",
      title: "Modern plugins.txt active markers",
      domains: ["load-order"],
      games: ["Fallout4", "SkyrimSE"],
      body: "Modern plugins.txt uses active markers.",
      related: ["load-order.plugins-legacy.v1"],
      seeAlso: ["xedit.files-list-object-shape.v1"],
    },
    {
      id: "load-order.legacy-only.v1",
      title: "Legacy only plugins handling",
      domains: ["load-order"],
      games: ["Fallout3", "FalloutNV"],
      body: "Legacy-only handling does not list Fallout4 as applicable.",
    },
  ];
}

async function withGetTool<T>(packs: LoadedPack[], fn: (tool: ReturnType<typeof makeGetTool>, registry: SessionRegistry) => Promise<T>): Promise<T> {
  const registry = openSessions(packs);
  try {
    return await fn(makeGetTool({ registry }), registry);
  } finally {
    registry.closeAll();
  }
}

test("get returns the base record when no game is requested", async () => {
  const pack = await buildLoadedPack("get-pack", baseRecords());
  await withGetTool([pack], async (tool) => {
    const env = await tool({ id: "archive-precedence.loose-over-archive.v1" });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data.record).toMatchObject({ id: "archive-precedence.loose-over-archive.v1", packId: "get-pack", title: "Loose files override archives" });
    expect(env.data.mergedVariants).toEqual([]);
    expect(env.data.sources).toEqual(env.data.record.sources);
  });
});

test("get merges a matching game variant into markdown body", async () => {
  const pack = await buildLoadedPack("get-pack", baseRecords());
  await withGetTool([pack], async (tool) => {
    const env = await tool({ id: "archive-precedence.loose-over-archive.v1", game: "Fallout4" });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data.mergedVariants).toEqual(["Fallout4"]);
    expect(env.data.appliesToRequestedGame).toBe(true);
    expect(env.data.record.bodyMd).toContain("## Game-specific notes");
    expect(env.data.record.bodyMd).toContain("- BA2 packaging and precombine/previs can affect the visible result.");
    expect(env.data.record.bodyMd).toContain("> [!WARNING] [PREVIS|high] Check precombine/previs before blaming plugin load order.");
  });
});

test("get returns base record and warning when game applies but no explicit variant exists", async () => {
  const pack = await buildLoadedPack("get-pack", baseRecords());
  await withGetTool([pack], async (tool) => {
    const env = await tool({ id: "load-order.plugins-modern.v1", game: "Fallout4" });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data.appliesToRequestedGame).toBe(true);
    expect(env.data.mergedVariants).toEqual([]);
    expect(env.warnings).toContainEqual({ code: "variant_not_found", severity: "MEDIUM", message: "No explicit variant for Fallout4; base record returned" });
  });
});

test("get returns base record and warning when requested game is excluded", async () => {
  const pack = await buildLoadedPack("get-pack", baseRecords());
  await withGetTool([pack], async (tool) => {
    const env = await tool({ id: "papyrus.oninit-vs-onload.v1", game: "FalloutNV" });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data.appliesToRequestedGame).toBe(false);
    expect(env.data.mergedVariants).toEqual([]);
    expect(env.warnings[0].message).toMatch(/explicitly excludes FalloutNV/);
  });
});

test("get returns base record and warning when requested game is not listed", async () => {
  const pack = await buildLoadedPack("get-pack", baseRecords());
  await withGetTool([pack], async (tool) => {
    const env = await tool({ id: "load-order.legacy-only.v1", game: "Fallout4" });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data.appliesToRequestedGame).toBe(false);
    expect(env.warnings[0].message).toMatch(/does not list Fallout4/);
  });
});

test("get refuses unknown ids with record_not_found", async () => {
  const pack = await buildLoadedPack("get-pack", baseRecords());
  await withGetTool([pack], async (tool) => {
    const env = await tool({ id: "missing.record.v1" });

    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("record_not_found");
  });
});

test("get refuses known id with unknown packId as record_not_found", async () => {
  const pack = await buildLoadedPack("get-pack", baseRecords());
  await withGetTool([pack], async (tool) => {
    const env = await tool({ id: "archive-precedence.loose-over-archive.v1", packId: "missing-pack" });

    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("record_not_found");
    expect(env.hint).toContain("Pack 'missing-pack' is not loaded");
  });
});

test("get warns when id is ambiguous across packs and uses first match", async () => {
  const a = await buildLoadedPack("pack-a", [{ id: "shared.record.v1", title: "A shared", domains: ["xedit"], games: ALL_GAMES, body: "Pack A body." }]);
  const b = await buildLoadedPack("pack-b", [{ id: "shared.record.v1", title: "B shared", domains: ["xedit"], games: ALL_GAMES, body: "Pack B body." }], "user");
  await withGetTool([a, b], async (tool) => {
    const env = await tool({ id: "shared.record.v1" });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data.record.packId).toBe("pack-a");
    expect(env.warnings[0].message).toContain("pack-a, pack-b");
  });
});

test("get disambiguates duplicate record id via packId", async () => {
  const a = await buildLoadedPack("pack-a", [{ id: "shared.record.v1", title: "A shared", domains: ["xedit"], games: ALL_GAMES, body: "Pack A body." }]);
  const b = await buildLoadedPack("pack-b", [{ id: "shared.record.v1", title: "B shared", domains: ["xedit"], games: ALL_GAMES, body: "Pack B body." }], "user");
  await withGetTool([a, b], async (tool) => {
    const env = await tool({ id: "shared.record.v1", packId: "pack-b" });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data.record.packId).toBe("pack-b");
    expect(env.warnings).toEqual([]);
  });
});

test("get refuses when variant deletion target is unmatched", async () => {
  const pack = await buildLoadedPack("get-pack", [
    {
      id: "archive-precedence.bad-deletion.v1",
      title: "Bad deletion",
      domains: ["archive-precedence"],
      games: ALL_GAMES,
      body: "Body that does not contain the deletion target.",
      variantsYaml: `variants:
  Fallout4:
    deletions:
      - Missing deletion target
`,
    },
  ]);
  await withGetTool([pack], async (tool) => {
    const env = await tool({ id: "archive-precedence.bad-deletion.v1", game: "Fallout4" });

    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("variant_deletion_unmatched");
  });
});

test("get validates args", async () => {
  const pack = await buildLoadedPack("get-pack", baseRecords());
  await withGetTool([pack], async (tool) => {
    const empty = await tool({ id: "" });
    const extra = await tool({ id: "archive-precedence.loose-over-archive.v1", extra: true });

    expect(empty.ok || empty.code).toBe("invalid_request");
    expect(extra.ok || extra.code).toBe("invalid_request");
  });
});

test("get refuses empty registry with not_loaded", async () => {
  const registry: SessionRegistry = { size: 0, byPackId: () => null, all: () => [], forEach: () => undefined, closeAll: () => undefined };
  const env = await makeGetTool({ registry })({ id: "archive-precedence.loose-over-archive.v1" });

  expect(env.ok).toBe(false);
  if (env.ok) throw new Error("expected refusal");
  expect(env.code).toBe("not_loaded");
});

test("get preserves related and seeAlso", async () => {
  const pack = await buildLoadedPack("get-pack", baseRecords());
  await withGetTool([pack], async (tool) => {
    const env = await tool({ id: "load-order.plugins-modern.v1" });

    expect(env.ok && env.data.record.related).toEqual(["load-order.plugins-legacy.v1"]);
    expect(env.ok && env.data.record.seeAlso).toEqual(["xedit.files-list-object-shape.v1"]);
  });
});

test("get passes sources through at top level and record level", async () => {
  const pack = await buildLoadedPack("get-pack", baseRecords());
  await withGetTool([pack], async (tool) => {
    const env = await tool({ id: "archive-precedence.loose-over-archive.v1" });

    expect(env.ok && env.data.sources).toEqual([{ kind: "project-internal-doc", ref: "tests/unit/tool-get.test.ts", sectionPath: "fixture" }]);
    expect(env.ok && env.data.sources).toEqual(env.ok && env.data.record.sources);
  });
});

test("get renders variant warning callouts in markdown", async () => {
  const pack = await buildLoadedPack("get-pack", baseRecords());
  await withGetTool([pack], async (tool) => {
    const env = await tool({ id: "archive-precedence.loose-over-archive.v1", game: "Fallout4" });

    expect(env.ok && env.data.record.bodyMd).toContain("> [!WARNING] [PREVIS|high] Check precombine/previs before blaming plugin load order.");
  });
});

// Hand-construct a glossary-shape pack: has a `records` table but is missing
// the `canonical_answer` column the standard records-shape pack carries. This
// mirrors `bgs-l10n-starfield-zhhans` and is the root cause of the
// "no such column: canonical_answer" runtime regression observed on 2026-06-23
// when bgs_kb_get iterated all loaded packs without a packId filter.
async function buildGlossaryShapePack(packId: string): Promise<LoadedPack> {
  const packRoot = await makeTempPack(`kb-glossary-${packId}-`);
  await writeFile(
    join(packRoot, "bgs-kb-meta.yml"),
    `packId: ${packId}\ndisplayName: ${packId} glossary fixture\nversion: 2026.06.23\nschemaVersion: 1\nminPluginVersion: 0.2.0\nowner: tests\nlicense: MIT\n`,
    "utf8",
  );
  const kbPath = join(packRoot, "kb.sqlite");
  const db = new DatabaseSync(kbPath, { readOnly: false });
  try {
    // Mirrors the real `bgs-l10n-starfield-zhhans` records-table shape (5 cols),
    // which has id/pack_id/kind/title/body_md but is missing canonical_answer
    // and all other standard records columns. The standard get.ts SELECT
    // succeeds through `body_md` and then fails on `canonical_answer`,
    // reproducing the live runtime error exactly.
    db.exec("CREATE TABLE records (id TEXT PRIMARY KEY, pack_id TEXT, kind TEXT, title TEXT, body_md TEXT)");
    db.exec("CREATE TABLE glossary_entries (id TEXT PRIMARY KEY, en TEXT, zh TEXT)");
    db.exec(`INSERT INTO glossary_entries (id, en, zh) VALUES ('e1','Vault','避难所')`);
  } finally {
    db.close();
  }
  const manifestPath = join(packRoot, "manifest.json");
  const manifest = {
    packId,
    displayName: `${packId} glossary fixture`,
    version: "2026.06.23",
    schemaVersion: 1,
    minPluginVersion: "0.2.0",
    games: ["Starfield"],
    domains: ["glossary"],
    engineFamilies: ["creation-engine-2"],
    owner: "tests",
    license: "MIT",
    recordCount: 1,
    builtAt: "2026-06-23T00:00:00.000Z",
    sha256: { "kb.sqlite": "test-fixture" },
  };
  await writeFile(manifestPath, JSON.stringify(manifest, null, 2), "utf8");
  return {
    packId,
    displayName: manifest.displayName,
    version: manifest.version,
    schemaVersion: manifest.schemaVersion,
    minPluginVersion: manifest.minPluginVersion,
    root: "bundled",
    rootPath: packRoot,
    packRoot,
    kbSqlitePath: kbPath,
    manifestPath,
    manifest: manifest as unknown as LoadedPack["manifest"],
    integrityOk: true,
    loadedAt,
  };
}

test("get tolerates glossary-shape packs (no canonical_answer column) when iterating without packId", async () => {
  const normalPack = await buildLoadedPack("normal-pack", baseRecords());
  const glossaryPack = await buildGlossaryShapePack("bgs-l10n-fixture");
  // Glossary pack listed FIRST so iteration hits the schema-mismatch path before the normal pack.
  await withGetTool([glossaryPack, normalPack], async (tool) => {
    const env = await tool({ id: "archive-precedence.loose-over-archive.v1" });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok envelope despite glossary pack present");
    expect(env.data.record).toMatchObject({ id: "archive-precedence.loose-over-archive.v1", packId: "normal-pack" });
    expect(env.warnings).toContainEqual(expect.objectContaining({ code: "skipped_non_record_packs", severity: "MEDIUM" }));
  });
});

test("get returns RECORD_NOT_FOUND with skippedPacks surfaced when only a glossary pack is loaded", async () => {
  const glossaryPack = await buildGlossaryShapePack("bgs-l10n-only");
  await withGetTool([glossaryPack], async (tool) => {
    const env = await tool({ id: "some.record.v1" });

    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("record_not_found");
    expect(env.detail).toMatchObject({ skippedPacks: [{ packId: "bgs-l10n-only", reason: "no_records_schema" }] });
  });
});
