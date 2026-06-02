# Agentic Cross-Game BGS Knowledge Base — Design Spec

- **Status:** Architecture approved 2026-06-02 (load-bearing gates A/B/C/D confirmed by maintainer); KB-1 implementation pending.
- **Roadmap entry:** `docs/internal/roadmap.md`, dated entry `2026-06-02 — Agentic cross-game KB architecture`.
- **Source survey reference:** `docs/internal/roadmap.md` § `Appendix: BGS modding source list (KB-4 fan-out research targets)`.
- **Related skills:** `skills/xedit-automation/`, `skills/xedit-conflict-audit/`, `skills/writing-bgs-load-order/`, `skills/setting-up-bgs-modding-environment/`.
- **Sister project:** `D:\TES5Edit-contrib\` (forked xEdit with automation daemon); MCP harness at `tools/xedit-mcp/`.

## 1. Goal

Ship an agentic cross-game Bethesda modding knowledge base addressable from any harness the plugin supports (OpenCode, Claude Code, Codex), serving structured curated knowledge for **Skyrim (LE/SE/AE/VR), Fallout 3, Fallout New Vegas, Fallout 4 (incl. FO4 VR), and Starfield**.

Target scale at full coverage: ~2500-3000 distinct knowledge items after de-duplication across the engine families (Gamebryo for FO3/FNV, Creation Engine for Skyrim family + FO4, Creation Engine 2 for Starfield).

The KB is **advisory**. The xEdit MCP's semantic readback remains authoritative for actual plugin / load-order state.

## 2. Non-goals

- Not a code-search MCP. Knowledge is curated facts about modding, not source code.
- Not a remote/hosted-only service. Offline-first operation is a hard requirement; network refresh is opt-in.
- Not a replacement for `xedit-mcp`. KB does not start xEdit, does not depend on daemon readiness, never holds plugin-file state.
- Not vector-embedding-first at v1. Embeddings are deferred to KB-6+ as an optional second signal.
- Not a per-modpack notes system. Modpack project-specific lessons live in `docs/dev-log.md` per `writing-modpack-devlog`. End-user KB packs are for *knowledge* that benefits other curators, not project notes.

## 3. Glossary

| Term | Meaning |
|---|---|
| Record | Single addressable knowledge unit. YAML frontmatter + Markdown body. Stable `id`. Has structured `appliesTo` and `sources`. |
| Pack | Versioned bundle of records + prebuilt SQLite index + manifest. Distribution unit. |
| Domain | Top-level taxonomy for records: `xedit`, `plugin-format`, `load-order`, `archive-precedence`, `papyrus`, `engine`, `tooling.spriggit`, `save-file`, `debugging`, `game-specific.vr`, `version-differences`. |
| Variant | Per-game overlay on a base record: adds caveats / warnings / additions specific to one game without duplicating the base fact. |
| Stage A | Cross-game subagents authoring the `core` pack. 4 parallel agents covering A1..A4 domains. |
| Stage B | Per-game subagents authoring per-game packs. 4 parallel agents covering B1..B4 games (B1 Skyrim, B2 FO4+VR, B3 FO3+FNV, B4 Starfield). |
| Game codes | `SkyrimLE` / `SkyrimSE` / `SkyrimAE` / `SkyrimVR` / `Fallout4` / `Fallout4VR` / `Fallout3` / `FalloutNV` / `Starfield`. Use these exact strings in `appliesTo.games`. |
| Engine families | `gamebryo` (FO3/FNV/Morrowind/Oblivion), `creation-engine` (Skyrim family + FO4), `creation-engine-2` (Starfield). |

## 4. Architecture overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Plugin user / agent harness                       │
│         (OpenCode / Claude Code / Codex; same MCP surface)           │
└──────────────────┬─────────────────────────────┬────────────────────┘
                   │                             │
                   │ stdio MCP                   │ stdio MCP
                   ▼                             ▼
       ┌─────────────────────┐         ┌─────────────────────┐
       │   xedit-mcp         │         │   bgs-kb-mcp        │
       │   (live xEdit)      │         │   (curated KB)      │
       │   7-stage harness   │         │   pack discovery    │
       │   daemon lifecycle  │         │   FTS5 retrieval    │
       └─────────┬───────────┘         └──────────┬──────────┘
                 │                                 │
                 ▼                                 ▼
       ┌────────────────────┐           ┌──────────────────────┐
       │  xEdit daemon       │          │  pack roots           │
       │  (Delphi process)   │          │  1. bundled           │
       │  MO2 VFS-launched   │          │  2. cache             │
       └────────────────────┘           │  3. user              │
                                        └──────────────────────┘
```

The two MCPs are siblings — independent state, independent lifecycle, independent updates. `bgs-kb-mcp` is **stateless w.r.t. the xEdit daemon**: KB queries succeed before MO2 / xEdit are configured.

## 5. Record schema

### 5.1 Source authoring format

Records are authored as Markdown files with YAML frontmatter:

```markdown
---
id: asset-precedence.loose-over-archive.v1
title: Loose files override archived assets at runtime
domains: [archive-precedence, file-conflicts, install-planning, diagnostics]
appliesTo:
  games: [Fallout4, Fallout4VR, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
  excludes: []
canonical:
  answer: |
    Loose files generally override archived assets at runtime.
    Plugin load order does not decide asset winners.
  confidence: high
variants:
  Fallout4:
    additions:
      - BA2 packaging matters; precombine/previs can be the real culprit even when plugin-side conflicts look clean.
    warnings:
      - code: PREVIS
        severity: HIGH
        text: Check precombine/previs integrity before concluding load order is the only problem.
  SkyrimSE:
    additions:
      - Behavior generation (Nemesis/FNIS) outputs can dominate visible animation behavior even when assets look correct.
queryKeys:
  - loose files win
  - archive precedence
  - BSA loose override
  - BA2 loose override
severity: high
confidence: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: §Asset precedence
  - kind: wiki
    url: https://tes5edit.github.io/docs/
    ref: xEdit Docs / Tome of xEdit
lastReviewed: 2026-06-02
schemaVersion: 1
---

# Loose files override archived assets at runtime

Body of the record in Markdown. Free-form prose for the nuanced explanation
the structured fields cannot carry — what the fact means, when it applies,
what to do, what NOT to do, verification / readback steps, caveats.
```

### 5.2 JSON Schema (Draft 2020-12, abbreviated)

Full schema lives at `knowledge/bgs-kb/schema/record.schema.json` (authored at KB-1a). Required fields are starred.

| Field | Type | Required | Notes |
|---|---|---|---|
| `id`* | `string` (slug) | ✓ | Stable, kebab-case, dotted-namespace, ends with `.v<N>` for the record's lifetime version. Reserved chars: none. Example: `xedit.conflict-winner.basics.v1`. |
| `title`* | `string` | ✓ | One-line human title. |
| `domains`* | `string[]` (enum) | ✓ | One or more from §3 Domain enum. |
| `appliesTo.games`* | `string[]` (game-code enum) | ✓ | At least one game code from §3. |
| `appliesTo.engineFamilies` | `string[]` | optional | Auto-derivable from games but supports cross-family records. |
| `appliesTo.excludes` | `string[]` (game-code enum) | optional | Explicit game-code exclusions when the body says "applies to ALL Creation Engine games EXCEPT X". |
| `canonical.answer`* | `string` | ✓ | 1-3 sentence canonical statement. The retrieval snippet defaults to this. |
| `canonical.confidence`* | `enum` | ✓ | `verified-official` / `verified-tooling` / `verified-project-doc` / `high` / `medium` / `low-community`. |
| `variants` | `object` | optional | Per-game overlay map. Keys are game codes; values are `{additions: string[], warnings: [{code, severity, text}], deletions: string[]}`. |
| `queryKeys` | `string[]` | optional | Lexical aliases boosted in FTS5 ranking. |
| `severity` | `enum` | optional | `low` / `medium` / `high` / `critical`. Affects sort tie-break. |
| `sources`* | `array of {kind, ref?, url?, sectionPath?}` | ✓ | At least one entry. `kind` enum: `official` / `tooling-docs` / `wiki` / `community-forum` / `github-issue` / `discord-pinned` / `project-skill` / `project-internal-doc`. Records without verified sources MUST set `confidence: low-community` and include a `needs verification` note in the body. |
| `lastReviewed`* | `string` (ISO date) | ✓ | yyyy-mm-dd. |
| `schemaVersion`* | `integer` | ✓ | Currently `1`. |
| `related` | `string[]` (ids) | optional | Other record ids forming a knowledge graph. |
| `seeAlso` | `string[]` (ids) | optional | Soft cross-references, lower-precedence than `related`. |

### 5.3 Variant merge semantics

When `bgs_kb_get` is called with a `game` filter, the server merges variants server-side:

1. Start with `canonical.answer` + body.
2. If `variants[<game>]` exists:
   - Append every `additions[i]` to the body as a bulleted "Game-specific note".
   - Render every `warnings[i]` as an inline callout: `[<severity>] [<code>] <text>`.
   - Apply `deletions[i]` strictly textually (the deletion target must match a substring in the canonical body; otherwise the merge fails with `variant_deletion_unmatched`).
3. Tag the response envelope with `mergedVariants: ["<game>"]` so the agent knows which overlay applied.

If `bgs_kb_get` is called WITHOUT a `game` filter, the response includes ALL variants under `variants[]` so the agent can pick. Default agent behavior should always pass `game` when known.

## 6. Pack format

```
<packId>/
  manifest.json                   # versioned, sha256, schema/plugin gates
  records/                        # source-authored .md with YAML frontmatter
    xedit/conflict-winner-basics.md
    load-order/plugins-txt-modern.md
    archive-precedence/loose-over-archive.md
    papyrus/oninit-vs-onload.md
    ...
  kb.sqlite                       # prebuilt index built from records/
```

Distribution artifact: `<packId>-<version>.zip` of the above tree (records/ rides along so source is always auditable next to the artifact).

### 6.1 manifest.json shape

```json
{
  "packId": "bgs-kb-core",
  "displayName": "BGS Modding Core Knowledge",
  "version": "2026.06.02",
  "schemaVersion": 1,
  "minPluginVersion": "0.2.0",
  "owner": "bgs-modding-superpowers maintainers",
  "license": "MIT",
  "sourceCommit": "abc123def456",
  "builtAt": "2026-06-02T00:00:00Z",
  "recordCount": 58,
  "domains": ["xedit", "load-order", "archive-precedence", "papyrus", "engine"],
  "games": ["SkyrimSE", "SkyrimAE", "SkyrimVR", "Fallout4", "Fallout4VR", "Fallout3", "FalloutNV", "Starfield"],
  "engineFamilies": ["gamebryo", "creation-engine", "creation-engine-2"],
  "sha256": {
    "kb.sqlite": "...64-hex..."
  }
}
```

`packId` reserved values: `bgs-kb-core`, `bgs-kb-skyrim`, `bgs-kb-fallout4`, `bgs-kb-fallout3`, `bgs-kb-falloutnv`, `bgs-kb-starfield`. End-user packs MUST use a different `packId` (collision check at load time).

## 7. SQLite schema

```sql
CREATE TABLE records (
  id            TEXT PRIMARY KEY,
  pack_id       TEXT NOT NULL,
  title         TEXT NOT NULL,
  body_md       TEXT NOT NULL,
  canonical_answer TEXT NOT NULL,
  applies_to_json  TEXT NOT NULL,     -- { games:[...], engineFamilies:[...], excludes:[...] }
  variants_json    TEXT,               -- { <game>: { additions:[], warnings:[], deletions:[] } }
  query_keys_json  TEXT,
  severity      TEXT,
  confidence    TEXT NOT NULL,
  sources_json  TEXT NOT NULL,         -- structured citations (mandatory)
  related_json  TEXT,
  see_also_json TEXT,
  last_reviewed TEXT NOT NULL,
  schema_version INTEGER NOT NULL
);

CREATE TABLE record_domains (
  record_id TEXT NOT NULL,
  domain    TEXT NOT NULL,
  PRIMARY KEY (record_id, domain)
);

CREATE TABLE record_games (
  record_id  TEXT NOT NULL,
  game       TEXT NOT NULL,
  confidence TEXT,                     -- per-game confidence override
  PRIMARY KEY (record_id, game)
);

CREATE TABLE record_excludes (
  record_id TEXT NOT NULL,
  game      TEXT NOT NULL,
  reason    TEXT,
  PRIMARY KEY (record_id, game)
);

CREATE TABLE record_engine_families (
  record_id TEXT NOT NULL,
  engine_family TEXT NOT NULL,
  PRIMARY KEY (record_id, engine_family)
);

CREATE TABLE pack_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE VIRTUAL TABLE records_fts USING fts5(
  title,
  body_md,
  query_keys,
  domains,
  content='records',
  content_rowid='rowid',
  tokenize='porter unicode61'
);

-- FTS5 triggers to keep the index in sync with `records`
CREATE TRIGGER records_ai AFTER INSERT ON records BEGIN
  INSERT INTO records_fts(rowid, title, body_md, query_keys, domains)
  VALUES (new.rowid, new.title, new.body_md,
          coalesce(new.query_keys_json, ''),
          (SELECT group_concat(domain, ' ') FROM record_domains WHERE record_id = new.id));
END;
-- (analogous AFTER DELETE / AFTER UPDATE triggers omitted for brevity)

-- Indexes for filter joins
CREATE INDEX idx_record_games_game ON record_games(game);
CREATE INDEX idx_record_domains_domain ON record_domains(domain);
CREATE INDEX idx_record_excludes_game ON record_excludes(game);
```

`pack_meta` mirrors `manifest.json` at runtime for quick access without re-reading the manifest file. Required keys: `packId`, `version`, `schemaVersion`, `minPluginVersion`, `recordCount`, `builtAt`, `sourceCommit`.

## 8. Pack discovery

The MCP discovers packs from three roots in **priority order**:

| Priority | Root | Path | Source |
|---|---|---|---|
| 1 | Bundled | `<plugin-root>/knowledge/bgs-kb/packs/` | Ships with the plugin tree (core pack only) |
| 2 | Cache | `%LOCALAPPDATA%/bgs-modding-superpowers/kb/packs/` | Downloaded via setting-up / maintaining skills |
| 3 | User | `$BGS_KB_USER_PACKS` (semicolon-separated absolute paths) | End-user authored packs |

At startup, the MCP scans each root, validates each pack's `manifest.json` against `schemaVersion` and `minPluginVersion` gates, and registers each `kb.sqlite` for query. **Duplicate `packId` across roots is an error** — the MCP refuses to start with `pack_id_collision` in the lifecycle envelope and logs which paths collided.

Conflict policy: there is no silent precedence between packs. Queries merge hits across all loaded packs; each hit is tagged with its `packId`, and `bgs_kb_query` accepts a `packIds: [...]` filter.

## 9. MCP tool contracts

### 9.1 Tool surface

| Tool | Purpose | Daemon dependence |
|---|---|---|
| `bgs_kb_status` | Pack discovery state, loaded packs, version map | none |
| `bgs_kb_query` | Ranked snippet hits with structured filters | none |
| `bgs_kb_get` | Full merged record by id (variant-merged for a game) | none |
| `bgs_kb_check_updates` | Compare local vs latest GitHub Release manifests | network (opt-in) |
| `bgs_kb_install_pack` | Download + verify + extract a Release asset to cache | network + filesystem |

All five tools are pure w.r.t. the xEdit daemon (no readiness check, no daemon spawn).

### 9.2 Detailed signatures

```ts
bgs_kb_status({}) -> Envelope<{
  packs: Array<{
    packId: string;
    displayName: string;
    version: string;
    schemaVersion: number;
    minPluginVersion: string;
    root: "bundled" | "cache" | "user";
    rootPath: string;
    recordCount: number;
    domains: string[];
    games: string[];
    integrityOk: boolean;          // sha256 check passed
    loadedAt: string;              // ISO timestamp
  }>;
  cacheRoot: string;
  userPackRoots: string[];
  totalRecordCount: number;
  schemaVersionSupported: number;
}>

bgs_kb_query({
  query: string;                     // free-text; tokenized + FTS5 MATCH
  games?: GameCode[];                // OR-filter; default = all loaded games
  domains?: Domain[];                // OR-filter; default = all
  toolchains?: string[];             // soft-boost match in query
  kinds?: ("rule"|"workflow"|"gotcha"|"explanation"|"source-map")[];
  packIds?: string[];                // restrict to specific packs
  maxResults?: number;               // default 5, max 20
  detailLevel?: "summary" | "expanded";   // default "summary"
  includeVariants?: boolean;         // default true
  includeSources?: boolean;          // default true
  cursor?: string;
}) -> Envelope<{
  normalizedQuery: object;
  hits: Array<{
    id: string;
    packId: string;
    title: string;
    score: number;                   // BM25-rank-normalized 0..1
    kind?: string;
    appliesTo: { games: string[]; engineFamilies: string[] };
    synopsis: string;                // canonical.answer
    snippet?: string;                // FTS5 snippet() of body
    variantNotes?: Array<{ game: string; text: string }>;
    sources?: Array<{ kind: string; ref?: string; url?: string }>;
    recordRef: { pack: string; path: string };
  }>;
  stats: {
    kbVersionMap: Record<string, string>;
    elapsedMs: number;
    totalCandidates: number;
  };
  nextCursor: string | null;
}>

bgs_kb_get({
  id: string;
  game?: GameCode;                   // if set, variants are merged server-side
  packId?: string;                   // disambiguate on collision
}) -> Envelope<{
  record: FullRecord;                // body_md after variant merge if game set
  mergedVariants: string[];          // game codes whose overlay was applied
  appliesToRequestedGame?: boolean;  // false if game is in excludes
  sources: Source[];
}>

bgs_kb_check_updates({
  packIds?: string[];                // default = all installed
}) -> Envelope<{
  updates: Array<{
    packId: string;
    currentVersion: string;
    latestVersion: string;
    upgradeAvailable: boolean;
    breakingChange: boolean;         // minPluginVersion violation
    releaseUrl: string;
    sha256: string;
    sizeBytes: number;
  }>;
}>

bgs_kb_install_pack({
  packId: string;
  version: string;                   // exact version; "latest" not allowed (explicit pin)
  dryRun?: boolean;                  // default false
}) -> Envelope<{
  installed: { packId: string; version: string; path: string };
  bytesDownloaded: number;
  sha256Verified: boolean;
  schemaVersionOk: boolean;
  minPluginVersionOk: boolean;
}>
```

### 9.3 Envelope shape

Reuse `xedit-mcp` envelope conventions for consistency:

```ts
type Envelope<T> = {
  ok: true;
  tool: string;
  summary: string;              // human-readable one-liner
  data: T;
  warnings: Warning[];
  status?: "completed" | "partial";
} | {
  ok: false;
  tool: string;
  summary: string;
  code: ErrorCode;
  hint?: string;
  detail?: object;
  warnings: Warning[];
};
```

### 9.4 Error codes

| Code | When | Recovery |
|---|---|---|
| `not_loaded` | Query before any pack loaded | Wait for startup; check `bgs_kb_status` |
| `record_not_found` | `get` with unknown id | Verify id via `query` first |
| `pack_id_collision` | Two roots have same packId | User must remove duplicate |
| `schema_version_unsupported` | Pack's `schemaVersion` > MCP's supported | Update plugin |
| `min_plugin_version_unmet` | Pack requires newer plugin | Update plugin or pin older pack version |
| `pack_integrity_failed` | sha256 mismatch | Re-download; abort install |
| `variant_deletion_unmatched` | Variant `deletions[]` target not in canonical body | Author fix needed |
| `download_failed` | Network/HTTP error during install | Retry; check release URL |
| `invalid_request` | Schema validation on tool args | Fix args |
| `internal_error` | Unexpected throw | Bug report |

## 10. Cross-game variant model — worked examples

### Example 1: Universal record, no variants needed

```yaml
id: xedit.formid-prefix-stripping.v1
title: xEdit daemon rejects FormIDs with 0x prefix
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical.answer: |
  The xEdit automation daemon rejects FormIDs with a 0x prefix. The MCP
  strips the prefix at the edge so callers can use either style.
sources:
  - kind: project-internal-doc
    ref: docs/internal/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md
    sectionPath: §"Now known"
```

No variants. Same fact applies identically to all xEdit-supported games.

### Example 2: Universal base with per-game additions

```yaml
id: asset-precedence.loose-over-archive.v1
title: Loose files override archived assets at runtime
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical.answer: |
  Loose files generally override archived assets at runtime; plugin load
  order alone does not decide asset winners.
variants:
  Fallout4:
    warnings:
      - code: PREVIS
        severity: HIGH
        text: BA2 packaging + precombine/previs can be the real winner surface; check before blaming load order.
  SkyrimSE:
    warnings:
      - code: GENERATED_OUTPUTS
        severity: MEDIUM
        text: Nemesis/FNIS behavior outputs can dominate animation behavior even when assets look correct.
```

Same base fact; FO4 + SkyrimSE get game-specific warnings about adjacent failure modes.

### Example 3: Exclusion via `excludes`

```yaml
id: papyrus.oninit-vs-onload.v1
title: OnInit fires once per save; use OnGameReload for reload detection
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  excludes: [Fallout3, FalloutNV]
canonical.answer: |
  OnInit fires only when the script first initializes — never on reload.
  Use RegisterForSingleUpdate / OnUpdate / OnGameReload for reload detection.
```

FO3 + FNV use GECK scripting, not Papyrus. Explicit exclusion prevents the retrieval surface from offering the fact to a non-Papyrus query.

### Example 4: Sibling records, not variants

When the substrate itself diverges, use sibling records linked via `related`, not variants.

```yaml
# Record 1
id: load-order.plugins-txt.modern.v1
title: Modern BGS plugins.txt uses asterisk prefix for active plugins
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
related: [load-order.plugins-txt.legacy.v1]
---
# Record 2 (separate file)
id: load-order.plugins-txt.legacy.v1
title: Legacy BGS plugins.txt is active-only; loadorder.txt holds the full order
appliesTo:
  games: [SkyrimLE, Fallout3, FalloutNV]
related: [load-order.plugins-txt.modern.v1]
```

## 11. Distribution model

### 11.1 Plugin-bundled (core pack only)

The plugin ships `core` pack inside the plugin tree:

```
<plugin-root>/knowledge/bgs-kb/packs/core/
  manifest.json
  records/
  kb.sqlite
```

Estimated size: ~1-3 MB. Works offline immediately.

Portable-plugin build script (`scripts/build-portable-plugin.ps1`) copies this tree into the portable output. Target 1 invariant: portable plugin stays small.

### 11.2 GitHub Release artifacts (per-game packs)

Per-game packs are NOT shipped inline. They are published as GitHub Release assets on this repo:

```
Release tag: kb-2026.06.02
Assets:
  bgs-kb-skyrim-2026.06.02.zip
  bgs-kb-fallout4-2026.06.02.zip
  bgs-kb-fallout3-2026.06.02.zip
  bgs-kb-falloutnv-2026.06.02.zip
  bgs-kb-starfield-2026.06.02.zip
  manifest-index.json  (lists all packs in this release with sha256 + minPluginVersion)
```

`bgs_kb_check_updates` fetches `manifest-index.json` to surface new versions.

### 11.3 Cache layout

```
%LOCALAPPDATA%/bgs-modding-superpowers/
  kb/
    packs/
      bgs-kb-fallout4/
        2026.06.02/
          manifest.json
          records/
          kb.sqlite
        current -> 2026.06.02         (junction or sentinel file)
      bgs-kb-skyrim/
        ...
    incoming/                          (partial-download staging; pruned on success)
```

Cache hygiene: `maintaining-modding-environments` skill prunes versions older than `current` by default, keeping the previous version as a fallback.

### 11.4 KB cadence ≠ plugin cadence

KB content fixes do NOT require a plugin re-release. A KB release publishes new pack artifacts; users pick up via `bgs_kb_check_updates` + `bgs_kb_install_pack`. The plugin pins only `schemaVersion` compatibility — new KB content is consumable as long as `schemaVersion` matches.

## 12. End-user authoring contract

End-user packs are first-class citizens. Authoring flow:

1. User creates a directory `<their-pack-root>/records/*.md` with the same YAML frontmatter schema as official packs.
2. User runs `node tools/bgs-kb-mcp/dist/cli.js build <their-pack-root>`.
3. CLI validates every record against the schema, builds `kb.sqlite`, writes `manifest.json` (auto-derives `packId` from a `bgs-kb-meta.yml` file at the pack root, or prompts).
4. User sets `BGS_KB_USER_PACKS=<their-pack-root>` (or uses the `maintaining-modding-environments` skill's "register a custom pack" subroutine).
5. MCP discovers + loads on next start. Queries merge user pack hits with official packs; each hit tagged by `packId`.

Constraints on end-user packs:

- `packId` MUST start with `user-` or another prefix the user controls; never collide with `bgs-kb-*`.
- `schemaVersion` must match the plugin's supported version.
- Records validate the same way as official records — same JSON Schema, same `sources` requirement.
- The MCP does NOT trust end-user packs more than official packs. Confidence + sources discipline applies.

## 13. Build CLI contract

`tools/bgs-kb-mcp/dist/cli.js`:

```
bgs-kb-mcp build <pack-root>            Build kb.sqlite + manifest.json from records/
bgs-kb-mcp validate <pack-root>          Validate all records against schema; exit 0/1
bgs-kb-mcp info <pack-root>              Print pack summary (packId, version, recordCount, domains, games)
bgs-kb-mcp diff <pack-a> <pack-b>        Diff two pack roots; useful for KB review
```

Build invariants:

- Every record must validate.
- Every record must have ≥1 source entry.
- `id` uniqueness check.
- `pack_id` consistency across all records.
- FTS5 triggers populated for every row.
- sha256 of `kb.sqlite` written into `manifest.json`.

## 14. Anti-copy guardrails (KB-4 fan-out gate)

The KB authoring process — especially Stage A / Stage B subagents at KB-4 — operates under a HARD RULE:

```
Do not hard-copy any text from WingedGuardian/skyrimvr-claude-toolkit
or any other external source. Paraphrase in our own voice and cite
the original (URL, repo path, wiki section) in the structured `sources`
field. Every record MUST include the `sources` field with at least one
verified entry. Unsourced facts get `confidence: low-community` and a
`needs verification` note in the body.

Subagents that hit a Cloudflare challenge MUST switch to the Playwright
harness rather than fall back to prior-based summarization. Sources
verified during the 2026-06-02 librarian survey:

  - simple HTTP works for: GitHub, UESP, openmw.org, enbdev.com,
    silverlock.org, ReShade, STEP wiki, ModDB, Bethesda Community Hub,
    TTW forums, Fandom wikis, Reddit (old.reddit.com), tooling docs sites.
  - Playwright required for: Sim Settlements, CK UESP mirror, GECK Wiki,
    Starfield Wiki, FO3/FNV Nexus pages, Bethesda Creations (JS app).
  - Dead/moved: forums.bethesda.net, www.creationkit.com.
```

Subagents receive the full curated source list from `docs/internal/roadmap.md` § Appendix as their starting point.

## 15. Acceptance criteria

Per `~/.config/opencode/memory/10-semantic-proof-and-acceptance-design.md`, acceptance is real production scenarios end-to-end, not surface signals.

### KB-1 acceptance

- 10+ seed records authored, all validate against the schema.
- Build CLI produces `kb.sqlite` deterministically given the same source tree (same `sourceCommit`).
- Raw SQL smoke: open the produced `kb.sqlite`, run a FTS5 MATCH query, get back ≥1 ranked hit with non-zero rank.
- The seed records exercise: at least one all-game record, one record with `excludes`, one record with variants, one record with multiple domains, one record with `related`/`seeAlso`.

### KB-2 acceptance

- MCP starts in `<plugin>/` and `<portable-plugin>/` trees, discovers core pack, reports `integrityOk: true` in `bgs_kb_status`.
- `bgs_kb_query({query: "loose files override", games: ["Fallout4"]})` returns the asset-precedence record with FO4 variant warning applied in the snippet.
- `bgs_kb_get({id: "papyrus.oninit-vs-onload.v1", game: "FalloutNV"})` returns `appliesToRequestedGame: false` and surfaces the exclusion.
- Negative case: query a Skyrim-only record with `games: ["Fallout3"]` filter; record is suppressed.
- Save-and-reload: stop MCP, start MCP, verify same pack set discovered (no transient state).
- Multi-pack: drop a fake user pack via `$BGS_KB_USER_PACKS`, verify hits tagged with the user `packId`.
- Latency: 95th percentile `bgs_kb_query` round-trip <50ms at 100 records.

### KB-3 acceptance

- `setting-up-bgs-modding-environment` invoked on a fresh machine: asks target games → fetches chosen packs → verifies sha256 → installs to cache → calls `bgs_kb_query` for smoke. Captures the full transcript under `.opencode/artifacts/kb/acceptance/kb-3-setup-<game-set>/`.
- `maintaining-modding-environments` exists as a tracked skill with a manifest, body, and at least 3 sub-workflows: "register custom pack", "check + apply KB updates", "prune cache".
- A blind oracle review confirms `setting-up` no longer contains ongoing-care content (it all moved to `maintaining`).

### KB-4 acceptance

- 8 sub-agent runs preserved as artifacts: 4 Stage A + 4 Stage B.
- Each pack passes the build CLI's validate step.
- Random sampling: pull 5 records from each pack; verify each has a verified `sources` entry pointing at a real URL (not a confabulation). Reviewer hits the URLs and confirms the source supports the claim.
- Anti-copy check: a manual diff between the WingedGuardian KNOWLEDGEBASE.md and ANY of our Skyrim records returns no sequences ≥40 characters long that match verbatim.
- Total record count ≥ 2000 across all 5 packs.

### KB-5 acceptance

- `xedit-automation` SKILL.md instructs agents to author KB records for durable facts (not to append to `xedit-knowledgebase.md`).
- `xedit-knowledgebase.md` either becomes a thin "how to query the KB" pointer OR is regenerated from KB records (deterministic, committed).
- One end-to-end test: agent encounters a new gotcha during a real xEdit task, authors a KB record, runs the build CLI, queries for it via `bgs_kb_query`, gets the new record back.

### KB-6 acceptance

- `bgs_kb_check_updates` against a staged Release surfaces an upgrade, declines breaking changes (mismatched minPluginVersion).
- `bgs_kb_install_pack` performs sha256 verification, refuses on mismatch with `pack_integrity_failed`.
- Eval harness: 20-query gold set with expected top-3 ids; CI run reports retrieval@3 and any regression.

## 16. Risks + carry-forwards

| Risk | Mitigation |
|---|---|
| Retrieval false negatives without embeddings | Strong metadata + aliases + symptoms + task tags + `related` links. Vector store reserved as KB-6+ option. |
| Stale folklore | `sources` mandatory; `confidence` + `lastReviewed` mandatory; unsourced facts visibly marked `low-community`. |
| Schema overreach | Keep prose body first-class. Maintainers will stop authoring if every nuance must fit a field. |
| xedit-mcp pollution | bgs-kb-mcp is independent. No daemon readiness. No xEdit lifecycle coupling. Enforced architecturally. |
| File-count bloat | Markdown source files per pack stay <500 each; large fan-out goes to per-game packs not per-record-explosion. |
| Plugin/KB compat drift | `minPluginVersion` + `schemaVersion` gates in `manifest.json`. MCP refuses to load incompatible packs with clear error. |
| `node:sqlite` FTS5 unavailability | Fallback: `better-sqlite3` with `node-pre-gyp` prebuilt binaries. Document choice at KB-2. WASM `sql.js` is the floor. |
| End-user pack abuse | `packId` namespace separation (`user-*`). Schema validation enforced. No special trust. |
| Cloudflare wall during KB-4 | Playwright switchover documented in Appendix; subagents instructed to never silently fall back to prior-based summarization. |
| Domain explosion | Domain enum is small + closed; new domains require schema bump. Records pick from the enum, not free strings. |

## 17. Non-acceptance

The following are NOT acceptance signals (per `10-semantic-proof-and-acceptance-design.md` rules):

- Build succeeded → not a semantic check; verify record content.
- Tests pass → necessary but not sufficient; verify retrieval matches design intent.
- LLM summary of the pack content sounds right → MUST be checked against actual SQLite content + sample queries.
- Manual GUI walkthrough on a single record → run the full query matrix.

## 18. References

- `docs/internal/roadmap.md` — current roadmap entry + Appendix source list.
- `docs/internal/superpowers/plans/2026-06-02-agentic-cross-game-kb.md` — implementation plan (KB-1..KB-6 task breakdown).
- `docs/internal/superpowers/specs/2026-05-26-xedit-skills-and-harness-mcp-design.md` — sibling MCP spec; envelope conventions reused.
- `tools/xedit-mcp/src/` — sibling MCP reference implementation; structural patterns reused (daemon-adapter, envelope, audit-line, runtime state machine).
- `~/.config/opencode/memory/10-semantic-proof-and-acceptance-design.md` — acceptance discipline.
- `~/.config/opencode/memory/40-low-intrusion-architecture.md` — sibling MCP placement rationale.
- `~/.config/opencode/memory/20-grounded-investigation-and-decision-making.md` — comparison-method rationale.
- `WingedGuardian/skyrimvr-claude-toolkit` — reference repo; structural inspiration only; **no content copied** per Section 14.
