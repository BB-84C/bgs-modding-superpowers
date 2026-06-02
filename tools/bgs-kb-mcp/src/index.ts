// =============================================================================
// bgs-kb-mcp — sibling MCP server for the BGS Modding knowledge base.
// =============================================================================
//
// Status: KB-1c bootstrap. The real server (pack discovery, bgs_kb_status /
// bgs_kb_query / bgs_kb_get, etc.) lands in KB-2 per:
//   docs/internal/superpowers/specs/2026-06-02-agentic-cross-game-kb-design.md
//   docs/internal/superpowers/plans/2026-06-02-agentic-cross-game-kb.md
//
// This module exists only so that:
//   - tsc has something to compile
//   - the package's `main` resolves
//   - downstream tooling (portable-plugin build, MCP registration) can be wired
//     against the final entry path without churn
//
// =============================================================================

export async function main(): Promise<void> {
  throw new Error(
    "bgs-kb-mcp server is not yet implemented. Pending KB-2; see docs/internal/superpowers/plans/2026-06-02-agentic-cross-game-kb.md",
  );
}

// Detect "invoked as the main entry" cross-platform (same pattern as
// xedit-mcp's index.ts). Errors out with a clear message until KB-2.
import { pathToFileURL } from "node:url";
const invokedAsMain = (() => {
  const argv = process.argv[1];
  if (!argv) return false;
  try {
    return import.meta.url === pathToFileURL(argv).href;
  } catch {
    return false;
  }
})();

if (invokedAsMain) {
  main().catch((e) => {
    console.error(e instanceof Error ? e.message : String(e));
    process.exit(1);
  });
}
