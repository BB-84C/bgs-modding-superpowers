import { expect, test } from "vitest";

import { formatDevStatus } from "../../src/dev-status.js";
import type { DiscoveryResult, LoadedPack, PackRoot } from "../../src/discovery/types.js";

function pack(args: { packId: string; root: PackRoot; packRoot: string; builtAt?: string; version?: string; recordCount?: number }): LoadedPack {
  return {
    packId: args.packId,
    displayName: `${args.packId} display`,
    version: args.version ?? "2026.06.02",
    schemaVersion: 1,
    minPluginVersion: "0.1.0",
    root: args.root,
    rootPath: `${args.root}-root`,
    packRoot: args.packRoot,
    kbSqlitePath: `${args.packRoot}/kb.sqlite`,
    manifestPath: `${args.packRoot}/manifest.json`,
    manifest: {
      packId: args.packId,
      displayName: `${args.packId} display`,
      version: args.version ?? "2026.06.02",
      schemaVersion: 1,
      minPluginVersion: "0.1.0",
      owner: "tests",
      license: "MIT",
      builtAt: args.builtAt as string,
      recordCount: args.recordCount ?? 1,
      domains: ["xedit"],
      games: ["Fallout4"],
      engineFamilies: ["creation-engine"],
      sha256: { "kb.sqlite": "0".repeat(64) },
    },
    integrityOk: true,
    loadedAt: "2026-06-11T00:00:00.000Z",
  };
}

function discovery(candidates: LoadedPack[]): DiscoveryResult {
  return {
    candidates,
    packs: [candidates[1]],
    skipped: [],
    collisions: [],
    rootsScanned: [],
    supportedSchemaVersion: 1,
    currentPluginVersion: "0.1.0",
  };
}

test("formats dev-status text preview with winners and overridden candidates", () => {
  const result = discovery([
    pack({ packId: "bgs-kb-core", root: "bundled", packRoot: "C:/bundled/core", builtAt: "2026-06-02T13:45:01.000Z", recordCount: 113 }),
    pack({ packId: "bgs-kb-core", root: "cache", packRoot: "C:/cache/core", builtAt: "2026-06-11T20:42:35.000Z", recordCount: 114 }),
  ]);

  const text = formatDevStatus(result, { context: "test-context" });

  expect(text).toContain("Pack discovery preview (test-context context)");
  expect(text).toContain("bgs-kb-core");
  expect(text).toContain("[cache]");
  expect(text).toContain("C:/cache/core");
  expect(text).toContain("114 records  <- WINNER");
  expect(text).toContain("[bundled]");
  expect(text).toContain("113 records  (overridden)");
  expect(text).toContain("Summary: 1 packs, 1 with multiple sources (precedence applied), 0 with no resolvable winner.");
});

test("formats dev-status JSON preview for one filtered pack", () => {
  const result = discovery([
    pack({ packId: "bgs-kb-core", root: "bundled", packRoot: "C:/bundled/core", builtAt: "2026-06-02T13:45:01.000Z" }),
    pack({ packId: "bgs-kb-core", root: "cache", packRoot: "C:/cache/core", builtAt: "2026-06-11T20:42:35.000Z" }),
    pack({ packId: "bgs-kb-fallout4", root: "bundled", packRoot: "C:/bundled/fallout4", builtAt: "2026-06-02T22:55:00.000Z" }),
  ]);

  const json = JSON.parse(formatDevStatus(result, { json: true, pack: "bgs-kb-core", context: "test-context" }));

  expect(json.summary).toEqual({ packs: 1, withMultipleSources: 1, noResolvableWinner: 0 });
  expect(json.packs).toHaveLength(1);
  expect(json.packs[0]).toMatchObject({ packId: "bgs-kb-core", winner: { root: "cache", path: "C:/cache/core" } });
  expect(json.packs[0].candidates).toEqual([
    expect.objectContaining({ root: "cache", path: "C:/cache/core", status: "winner" }),
    expect.objectContaining({ root: "bundled", path: "C:/bundled/core", status: "overridden" }),
  ]);
});
