# 05 — Glossary and KB Integration

## Architectural decision

The translation glossary is **not** a parallel data system. It rides on the existing `bgs-kb-*` knowledge base infrastructure as a new record kind.

This means:
- One mental model for users (KB packs handle both knowledge and terminology)
- One distribution channel (GitHub releases, manifest-index.json)
- One update path (`bgs_kb_check_updates`)
- One overlay mechanism (`$BGS_KB_USER_PACKS` env)
- One search surface for agents (`bgs_kb_query`)
- The translator reads glossary records by directly opening the same SQLite pack stores (faster than going through MCP tools for high-frequency lookups during batch planning)

---

## 1. The four-layer composition model

### 1.1 Resolution semantics

The glossary is **not** "hit-and-stop at the highest-priority match." It is a **composing** resolution. A single source string can have multiple terms inside it, and different terms can match at different layers:

```
Source string: "The Khajiit merchant in Whiterun sold a Daedric sword."
                    ↑                ↑                       ↑
            player_override    vanilla_canon          vanilla_canon
            (override)         ("白漫城")             ("魔族")
```

Each term is resolved independently. The composition rule per term:

```python
def resolve_term(term: str, layers: dict[str, list[GlossaryEntry]]) -> ResolvedTerm:
    # do_not_translate is a hard veto
    if entry := find_match(term, layers["do_not_translate"]):
        return ResolvedTerm(action="preserve_verbatim", entry=entry)
    
    # Layered fallback: player > mod > vanilla
    for scope in ("player", "mod_scoped", "vanilla_canon"):
        if entry := find_match(term, layers[scope]):
            return ResolvedTerm(action="translate_to", entry=entry)
    
    return ResolvedTerm(action="no_constraint", entry=None)
```

But this resolution runs **per term**, not per string. The full source string can pull rules from all four layers simultaneously.

### 1.2 What feeds the prompt

The batcher collects ALL `GlossaryEntry` records that have at least one `source_aliases` matching any string in the batch. Those records (deduplicated, sorted by scope priority, then alphabetically) are rendered into the `${glossary_subset_rendered}` slot of the system prompt.

The `${do_not_translate_list}` slot is the union of:
- All `do_not_translate`-scope glossary records whose source matches any batch string
- All heuristic skip-rule matches (built-in regexes) that happened to leave portions of the source untouched

### 1.3 The four layers

| Layer | Source | Mutation path |
|---|---|---|
| `do_not_translate` | Bundled core pack examples + user/project overlay | User: Tk Glossary tab → Add. Agent: via `bgs_kb` MCP server (or by writing a user pack — see §3) |
| `player_override` | User overlay pack via `$BGS_KB_USER_PACKS` | User editable in Tk Glossary tab; backed by TOML files on disk |
| `mod_scoped` | Community-published `bgs-kb-l10n-<game>-<modslug>-<src>-<tgt>` packs OR entries inside the canonical language pack with `scope_key` set to mod name | Pack maintainer publishes new pack version; user installs via `bgs_kb_install_pack` |
| `vanilla_canon` | Community-published `bgs-kb-l10n-<game>-<src>-<tgt>` packs | Pack maintainer publishes new pack version; user installs |

Resolution priority (when multiple layers match the same term): `do_not_translate` > `player_override` > `mod_scoped` > `vanilla_canon`.

---

## 2. The `glossary-entry` record kind

A new KB record kind alongside the existing `rule | workflow | gotcha | explanation | source-map`.

### 2.1 Record schema

```yaml
- id: l10n.skyrim.character.whiterun.en-zhcn
  kind: glossary-entry
  appliesTo:
    games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  glossary:
    source: "Whiterun"
    sourceAliases: ["Whiterun's", "Whiterun,", "in Whiterun"]
    sourceLang: "en"
    target: "白漫城"
    targetAliases: ["白漫"]
    targetLang: "zh-cn"
    scope: "vanilla"                # vanilla | mod | player | do_not_translate
    scopeKey: null                  # required for scope=mod (mod slug); null otherwise
    category: "place"               # character | faction | place | item | spell | lore_term | ui_label | brand
    confidence: "canonical"         # canonical | preferred | candidate
    notes: "Capital of Whiterun Hold; commonly used proper noun."
  sources:
    - kind: community-consensus
      ref: "Skyrim 中文社区共识"
      url: "https://..."
```

### 2.2 Mandatory fields

- `id`: stable, follows pattern `l10n.<game>.<category>.<slug>.<src>-<tgt>`
- `kind`: literal `glossary-entry`
- `appliesTo.games`: which games this entry applies to
- `glossary.source`: canonical source-language form
- `glossary.sourceLang`, `glossary.targetLang`: language codes
- `glossary.scope`: which of the four layers
- `glossary.category`: for classification and UI grouping

### 2.3 Optional fields

- `sourceAliases`, `targetAliases`: variant forms (plurals, possessives, common case-mangles)
- `scopeKey`: for `scope=mod`, the mod slug this entry is restricted to
- `confidence`: tells the LLM whether this is a hard rule or a preference
- `notes`: explanation, useful for cross-translator consistency
- `sources`: provenance citations (consistent with other KB record kinds)

### 2.4 Special `do_not_translate` entries

For DNT, `target` field is interpreted as "same as source." Example:

```yaml
- id: l10n.skyrim.brand.mod_author_handle.en-zhcn
  kind: glossary-entry
  appliesTo:
    games: [SkyrimSE]
  glossary:
    source: "EnaiSiaion"
    sourceLang: "en"
    target: "EnaiSiaion"            # Preserved verbatim
    targetLang: "zh-cn"
    scope: "do_not_translate"
    category: "brand"
    confidence: "canonical"
    notes: "Mod author handle; never translate."
```

---

## 3. Pack ID conventions

### 3.1 Canonical community packs

```
bgs-kb-l10n-skyrim-en-zhcn           # All scopes (vanilla, do_not_translate) for Skyrim EN→ZH-CN
bgs-kb-l10n-fallout4-en-zhcn
bgs-kb-l10n-starfield-en-zhcn
bgs-kb-l10n-skyrim-en-fr
bgs-kb-l10n-skyrim-en-de
... etc
```

These are community-maintained. They include `vanilla_canon` and `do_not_translate` entries primarily. Distributed via GitHub Release per `bgs-kb` core conventions.

### 3.2 Mod-specific packs (optional)

When a mod is large enough to warrant its own glossary:

```
bgs-kb-l10n-skyrim-requiem-en-zhcn
bgs-kb-l10n-fallout4-falsegen-en-zhcn
```

These contain `mod_scoped` entries (with `scopeKey = "requiem"` etc.). Optional; small mods can put their `mod_scoped` entries inside the canonical pack with `scopeKey` set.

### 3.3 User-overlay packs (per-machine, via `$BGS_KB_USER_PACKS`)

```
~/.bgs-modding-superpowers/kb/user-packs/
└── translator-overrides-en-zhcn/
    ├── manifest.toml
    └── records/
        ├── player-preferences.toml
        └── project-do-not-translate.toml
```

User-overlay packs hold:
- `player_override` entries ("I prefer 凯季特 to 虎人 for Khajiit")
- Project-scoped `do_not_translate` entries (mod author handles for the current project)

The Tk Glossary tab is the primary mutation surface for these.

---

## 4. How the translator reads glossary records

### 4.1 Reading via direct SQLite (not MCP)

For runtime performance during batch planning, the translator opens the bgs-kb pack SQLite files directly in read-only mode. This avoids per-query MCP roundtrip overhead.

```python
# bgs_translator/kb/reader.py
class KBGlossaryReader:
    def __init__(self, kb_root: Path):
        # Discover pack DBs via bgs-kb's manifest pattern
        self.pack_dbs: list[Path] = list(kb_root.glob("packs/*/store.sqlite"))
        self.user_pack_dbs: list[Path] = list(kb_root.glob("user-packs/*/store.sqlite"))
        # Open each read-only
        self.conns: list[sqlite3.Connection] = [
            sqlite3.connect(f"file:{db}?mode=ro", uri=True) 
            for db in self.pack_dbs + self.user_pack_dbs
        ]
    
    def query(self, source_strings: list[str], target_lang: str, 
              game: str, mod_slug: str | None = None) -> list[GlossaryEntry]:
        """Return all matching glossary entries for the given source strings."""
        # Across all conns, query the glossary_entry records table
        # Filter by:
        #   - target_lang
        #   - applies_to_games contains game
        #   - source or source_aliases substring-matches any source_string
        #   - scope_key matches mod_slug for scope=mod entries (else null)
        # Return deduplicated by id, sorted by scope priority
        ...
```

### 4.2 Why direct SQLite and not `bgs_kb_query` MCP

- Batch planning happens once per batch and queries 30-50 strings against potentially thousands of glossary entries. MCP roundtrip is too slow.
- bgs-kb's `bgs_kb_query` is FTS5-based BM25 ranking, optimized for "what's the top-3 results for this prose query." We want "every match for every alias of every entry against these strings." Different shape.
- Direct SQLite respects the same packs structure as bgs-kb. We're a sibling consumer, not a sidestep.

### 4.3 When the translator uses `bgs_kb_query` MCP

For human-facing queries from the agent ("Hey agent, how does the community usually translate 'Daedra' to Chinese?"), the agent uses `bgs_kb_query` directly. That's not the translator's lookup path; that's the agent's general KB usage.

---

## 5. Tk Glossary tab integration

See `07-tk-control-panel.md` §3.6 for full widget detail.

Glossary tab provides:
- Four sub-tabs for the four scopes (read-only display for `vanilla_canon` and `mod_scoped` from packs; read-write for `player_override` and `do_not_translate`)
- Search box (substring match across all aliases)
- Add/Edit/Delete buttons (only for the writable scopes)
- "Source of entry" badge (which pack it came from)

User mutations go to the user-overlay pack at `~/.bgs-modding-superpowers/kb/user-packs/translator-overrides-<src>-<tgt>/`. If the pack doesn't exist, it's created automatically on first add.

---

## 6. Importing existing xTranslator XML dictionaries

The user can have years of accumulated translation memory in xTranslator's XML or SST format. We provide a **one-shot conversion script** (not a CLI subcommand) to ingest these into KB pack form:

```bash
# Run as a one-off, not as part of normal workflow
python -m bgs_translator.tools.import_xtranslator_xml \
    --input ~/Downloads/some-xtranslator-dict.xml \
    --game SkyrimSE \
    --target-lang zh-cn \
    --scope mod_scoped \
    --mod-slug requiem \
    --output-pack-id l10n-skyrim-requiem-en-zhcn-imported
```

The script:
1. Parses the XML per `SSTXMLRessources` schema (per xTranslator's `TESVT_XMLFunc.pas`)
2. Maps `<String>` entries to `glossary-entry` records:
   - `<Source>` text → `glossary.source`
   - `<Dest>` text → `glossary.target`
   - `<REC>` text "WEAP:FULL" → `category` (mapped from record sig)
3. Generates a user pack under `~/.bgs-modding-superpowers/kb/user-packs/<pack-id>/`
4. Reports import statistics (count, dedup, conflicts)

This is **not** a CLI subcommand because it's a one-time operation per user, and it touches KB pack structure (which is bgs-kb territory, not translator territory). Keeping it as a standalone script keeps the translator CLI focused.

A similar standalone script can ingest SST files via the SST reader (`xtranslator-sst-to-kb-pack.py`), useful for ingesting `.sst` files distributed on Nexus.

### 6.1 Conflict resolution during import

When the same source maps to different targets across input XML files (e.g., two different user dictionaries disagree):

- Report the conflict
- Default behavior: skip the second one, keep the first
- `--prefer-newer` flag to override
- `--conflicts-to-file <path>` to dump conflicts as JSON for manual review

---

## 7. Glossary rendering in system prompt

The `${glossary_subset_rendered}` slot is filled by:

```
术语表（必须严格遵循）：
- Whiterun → 白漫城 (place, canonical)
- Khajiit → 凯季特 (character, player override)
- Daedric → 魔族 (lore_term, canonical)
- Iron Sword → 铁剑 (item, canonical, prefer this exact form)
```

Format rules:
- One entry per line
- `source → target (category, confidence)`
- For `confidence = canonical`, no extra hint
- For `confidence = preferred`, add "prefer this exact form"
- For `confidence = candidate`, add "candidate; LLM may use judgment"
- Maximum 50 entries per prompt (trimmed by relevance score if exceeded — see §8)

For the `${do_not_translate_list}` slot:

```
禁止翻译（保持原文）：
- EnaiSiaion
- Requiem
- $MyMCMToken
- SKSE
```

Just verbatim source forms.

---

## 8. Glossary scoring for batch prompts

When the glossary subset has too many entries to fit in the prompt:

Score = (occurrence count in batch) × (scope priority weight) × (confidence weight)

Scope priority weights:
- `do_not_translate`: ∞ (always included)
- `player_override`: 4.0
- `mod_scoped`: 2.0
- `vanilla_canon`: 1.0

Confidence weights:
- `canonical`: 1.0
- `preferred`: 0.8
- `candidate`: 0.5

Top 50 by score are included. If more than 50 DNT entries match, all DNT entries are included (the soft cap doesn't apply to hard rules).

---

## 9. Migration plan: bgs-kb integration touchpoints

This PRD adds a new record kind to bgs-kb. That requires bgs-kb-side work tracked separately:

| bgs-kb work item | Owner | Trigger |
|---|---|---|
| Add `glossary-entry` to the record kind enum | bgs-kb team | Before any l10n pack ships |
| Update `bgs_kb_query` to support `--kinds glossary-entry` filter | bgs-kb team | Before agent uses `bgs_kb_query` for translation glossary lookups |
| Document `glossary-entry` schema in bgs-kb spec | bgs-kb team | Before community publishes packs |
| Set up `bgs-kb-l10n-skyrim-en-zhcn` seed pack | community | After bgs-kb-side support lands |

The bgs-translator codebase can move ahead independently — it reads SQLite directly, so as long as the `glossary-entry` records exist in the pack DBs (whatever pack-construction process puts them there), the translator works.

But the agent-facing `bgs_kb_query` integration depends on the bgs-kb-side update.

The user has pre-approved touching the bgs-kb logic for this integration; see `08-persistence-and-paths.md` §3 for the related KB cache path migration.
