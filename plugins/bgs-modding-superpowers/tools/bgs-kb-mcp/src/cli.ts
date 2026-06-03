#!/usr/bin/env node
// =============================================================================
// bgs-kb-mcp CLI — pack-build / validate / info / render
// =============================================================================
//
// Status: KB-1e. `build` is implemented; the other subcommands are skeletons.
// Subcommands land in:
//   KB-1e — build  (build kb.sqlite + manifest.json from records/)
//   KB-1f — validate / info
//   KB-5  — render (regenerate xedit-knowledgebase.md from KB records)
//
// =============================================================================

import { buildPack, BuildValidationError } from "./build/index.js";
import { readRecords } from "./build/read-records.js";
import { formatValidationError } from "./build/validate.js";
import { validateRecords } from "./build/validate.js";
import { formatPruneCacheResult, pruneCache } from "./cache/prune-cache.js";
import { defaultCacheRoot } from "./discovery/resolve-roots.js";
import { formatInfo } from "./info/format.js";
import { gatherInfo } from "./info/index.js";
import { resolve } from "node:path";

const args = process.argv.slice(2);

if (args.length === 0 || args[0] === "--help" || args[0] === "-h") {
  console.log(`bgs-kb-mcp CLI (v0.1.0 — KB-1c skeleton)

Usage:
  bgs-kb-mcp build <pack-root>       Build kb.sqlite + manifest.json from records/  (KB-1e)
  bgs-kb-mcp validate <pack-root>    Validate all records against schema            (KB-1f)
  bgs-kb-mcp info <pack-root>        Print pack summary                             (KB-1f)
  bgs-kb-mcp prune-cache [--dry-run] Keep current + previous cached pack versions   (KB-6d)
  bgs-kb-mcp render <pack-root>      Render legacy markdown handbook from records   (KB-5)

Currently implemented: build, validate, info. Other subcommands return exit 2
with a pointer to the relevant phase.
`);
  process.exit(args.length === 0 ? 1 : 0);
}

const sub = args[0];

if (sub === "build") {
  const packRoot = args[1];
  if (!packRoot) {
    console.error("bgs-kb-mcp build: missing <pack-root>");
    process.exit(2);
  }

  try {
    const result = await buildPack(packRoot);
    console.log(`Built pack at ${result.packRoot}
  records:  ${result.recordCount}
  domains:  ${result.manifest.domains.join(", ")}
  games:    ${result.manifest.games.join(", ")}
  output:   ${result.kbSqlitePath} (sha256 ${result.sha256})
  manifest: ${result.manifestPath}`);
    process.exit(0);
  } catch (error) {
    if (error instanceof BuildValidationError) {
      for (const recordError of error.validationErrors) {
        for (const validationError of recordError.errors) {
          console.error(formatValidationError(recordError.sourcePath, validationError));
        }
      }
      process.exit(1);
    }
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(2);
  }
}

if (sub === "validate") {
  const packRoot = args[1];
  if (!packRoot) {
    console.error("bgs-kb-mcp validate: missing <pack-root>");
    process.exit(2);
  }

  const resolvedPackRoot = resolve(packRoot);
  try {
    const records = await readRecords(resolvedPackRoot);
    const result = validateRecords(records, resolvedPackRoot);
    if (result.errors.length === 0) {
      const byDomain = new Map<string, number>();
      for (const record of result.valid) {
        for (const domain of record.domains) byDomain.set(domain, (byDomain.get(domain) ?? 0) + 1);
      }
      const summary = [...byDomain.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([domain, count]) => `${domain}: ${count}`)
        .join(", ");
      console.log(`OK: ${result.valid.length} records valid in ${resolvedPackRoot}`);
      console.log(`summary: ${summary}`);
      process.exit(0);
    }

    for (const recordError of result.errors) {
      for (const validationError of recordError.errors) {
        console.error(formatValidationError(recordError.sourcePath, validationError));
      }
    }
    console.error(`FAIL: ${result.valid.length} valid, ${result.errors.length} failing in ${resolvedPackRoot}`);
    process.exit(1);
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    process.exit(2);
  }
}

if (sub === "info") {
  const packRoot = args[1];
  if (!packRoot) {
    console.error("bgs-kb-mcp info: missing <pack-root>");
    process.exit(2);
  }

  try {
    const info = await gatherInfo(packRoot);
    process.stdout.write(formatInfo(info));
    process.exit(0);
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    process.exit(2);
  }
}

if (sub === "prune-cache") {
  const extra = args.slice(1).filter((arg) => arg !== "--dry-run");
  if (extra.length > 0) {
    console.error(`bgs-kb-mcp prune-cache: unsupported argument(s): ${extra.join(", ")}`);
    process.exit(2);
  }
  try {
    const result = await pruneCache(defaultCacheRoot(), { dryRun: args.includes("--dry-run") });
    process.stdout.write(formatPruneCacheResult(result));
    process.exit(0);
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    process.exit(2);
  }
}

console.error(
  `bgs-kb-mcp CLI: subcommand '${sub}' is not yet implemented. ` +
    `See docs/internal/superpowers/plans/2026-06-02-agentic-cross-game-kb.md for the implementing phase.`,
);
process.exit(2);
