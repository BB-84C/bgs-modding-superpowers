#!/usr/bin/env node
// =============================================================================
// bgs-kb-mcp CLI — pack-build / validate / info / render
// =============================================================================
//
// Status: KB-1c skeleton. Only --help is implemented at this point.
// Subcommands land in:
//   KB-1e — build  (build kb.sqlite + manifest.json from records/)
//   KB-1f — validate / info
//   KB-5  — render (regenerate xedit-knowledgebase.md from KB records)
//
// =============================================================================

const args = process.argv.slice(2);

if (args.length === 0 || args[0] === "--help" || args[0] === "-h") {
  console.log(`bgs-kb-mcp CLI (v0.1.0 — KB-1c skeleton)

Usage:
  bgs-kb-mcp build <pack-root>       Build kb.sqlite + manifest.json from records/  (KB-1e)
  bgs-kb-mcp validate <pack-root>    Validate all records against schema            (KB-1f)
  bgs-kb-mcp info <pack-root>        Print pack summary                             (KB-1f)
  bgs-kb-mcp render <pack-root>      Render legacy markdown handbook from records   (KB-5)

Currently only --help is implemented. Subcommands return exit 2 with a pointer
to the relevant phase.
`);
  process.exit(args.length === 0 ? 1 : 0);
}

const sub = args[0];
console.error(
  `bgs-kb-mcp CLI: subcommand '${sub}' is not yet implemented. ` +
    `See docs/internal/superpowers/plans/2026-06-02-agentic-cross-game-kb.md for the implementing phase.`,
);
process.exit(2);
