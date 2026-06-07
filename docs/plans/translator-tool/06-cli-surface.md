# 06 — CLI Surface

CLI is the **agent-facing** interface. Humans use the GUI for config/monitoring; the CLI is how the agent drives work.

Design constraints:
- All read commands return JSON by default. `--text` flag formats for humans on stdout when needed.
- All mutation commands return a uniform envelope. Success: `{"ok": true, "data": {...}}`. Failure: `{"ok": false, "error": {"code": "...", "message": "...", "details": {...}}}`.
- Stable `error.code` values; agents branch on `code`, never on `message` text.
- Exit codes: `0` = success, `1` = recoverable error (env, file, network), `2` = invalid args, `3` = irrecoverable internal error.

---

## 1. Command tree

```
xtl
├── project
│   ├── init           # Create new project
│   ├── list           # List known projects
│   ├── status         # Project state, counts, costs
│   ├── archive        # Close out project (soft delete)
│   ├── rescan         # Re-parse source plugin (handles mod version updates)
│   └── export         # Emit final SST(s)
├── inspect
│   ├── plugin         # High-level plugin stats
│   ├── signatures     # Per-signature translatable counts
│   ├── entries        # Filtered entry list
│   ├── entry          # Single entry detail
│   └── orphans        # Entries with oldData status
├── edit
│   ├── entry          # Single entry mutation
│   ├── bulk           # JSONL bulk mutation
│   ├── status         # Change status only (without changing translation)
│   └── revert         # Revert to untranslated / restore source
├── batch
│   ├── plan           # Build BatchPlan; return prompt preview
│   ├── run            # Execute a plan; return run_id, exit immediately
│   ├── status         # Run/batch status
│   ├── cancel         # Cancel run or specific client
│   └── logs           # Tail run logs
├── profile
│   ├── add            # Add provider profile (key reference, not key value)
│   ├── list           # List profiles
│   ├── show           # Show one profile (key masked)
│   ├── edit           # Edit profile
│   ├── activate       # Set active default
│   └── probe          # Capability probe
├── validate
│   ├── project        # Run all validators across project
│   └── sst            # Validate single SST file (round-trip)
├── config
│   ├── show           # Current global settings
│   └── set            # Update a setting
├── gui                # Launch Tk control panel
└── version            # Tool version + emitted SST version + compat info
```

---

## 2. Envelope shapes

### Success

```json
{
  "ok": true,
  "data": { ... }
}
```

### Failure

```json
{
  "ok": false,
  "error": {
    "code": "string_stable_id",
    "message": "Human-readable explanation",
    "details": { "...": "..." }
  }
}
```

### Common error codes

| Code | When |
|---|---|
| `project_not_found` | Named project does not exist |
| `plugin_not_found` | Source plugin path is invalid |
| `parse_error` | Plugin binary parse failed |
| `invalid_argument` | CLI arg validation failed |
| `entry_not_found` | inspect/edit by key didn't match |
| `profile_not_found` | Profile name not registered |
| `profile_missing_key` | Profile references env var that is not set |
| `cost_cap_exceeded` | Per-profile or per-project cost cap hit |
| `rate_limit_halted` | Profile in 3-consecutive-429 halt state |
| `validation_failed_unrecoverable` | Validator failed after retry budget |
| `run_not_found` | batch status / cancel referenced unknown run |
| `network_error` | HTTP transport failure |
| `provider_error` | Provider returned error in response |
| `not_implemented` | Reserved for future features |

---

## 3. Command reference

### 3.1 Project lifecycle

#### `xtl project init`

```
xtl project init <name>
    --source-plugin <path>         # Required. Path to .esp/.esm/.esl
    --game <game-code>             # Required. SkyrimSE | SkyrimAE | SkyrimLE | SkyrimVR | Fallout4 | Fallout4VR | Fallout3 | FalloutNV | Fallout76 | Starfield | Oblivion | Morrowind
    --source-lang <code>           # Required. e.g. en
    --target-lang <code>           # Required. e.g. zh-cn
    [--profile <name>]             # Active profile for this project; defaults to global active
    [--no-starfield-dummy-fill]    # Disable Starfield 9-fill (default on for Starfield)
    [--prompt-template <name>]     # Override default prompt template
```

Returns:
```json
{
  "ok": true,
  "data": {
    "project": "adwryos-zhcn",
    "project_dir": "/Users/u/.bgs-modding-superpowers/translator/projects/adwryos-zhcn",
    "game": "Starfield",
    "source_lang": "en",
    "target_lang": "zh-cn",
    "starfield_dummy_fill": true,
    "plugin_sha256": "...",
    "extracted_units": 642,
    "by_signature": {"WEAP": 78, "INFO": 412, "BOOK": 12, ...}
  }
}
```

#### `xtl project list`

```
xtl project list
```

Returns array of projects with status summary.

#### `xtl project status <name>`

```
xtl project status <name>
```

Returns full project state: plugins, total/translated/partial/orphan counts, current run if any, costs.

#### `xtl project rescan <name>`

```
xtl project rescan <name>
```

Re-parses source plugin. Detects entries that changed source string (per merge key `(edid, signature, field, index)` + source-string hash diff). Marks them as `incompleteTrans` per xTranslator partial-translation convention. New entries enter as untranslated. Removed entries become `oldData` orphans (preserved by default).

#### `xtl project export <name>`

```
xtl project export <name>
    [--format sst|sst+xml]         # Default sst
    [--out <dir>]                  # Override default exports/ directory
```

Returns list of emitted files.

For Starfield projects with `starfield_dummy_fill = true`, returns 9 file paths.

#### `xtl project archive <name>`

```
xtl project archive <name>
```

Soft delete: moves project dir to `projects/_archived/<name>-<timestamp>/`. Idempotent.

### 3.2 Inspection (Mode B reads)

#### `xtl inspect plugin <project>`

```
xtl inspect plugin <project>
```

Returns: `{plugin, total_units, by_signature: {...}, by_status: {...}, by_list_index: {...}}`

#### `xtl inspect signatures <project>`

```
xtl inspect signatures <project>
```

Returns per-signature counts with field breakdown.

#### `xtl inspect entries <project>`

```
xtl inspect entries <project>
    [--signature WEAP]                 # Filter by record sig
    [--field FULL]                     # Filter by subrecord sig
    [--status untranslated|partial|translated|locked|orphan]
    [--edid-contains <substr>]         # EditorID substring (case-insensitive)
    [--source-contains <substr>]       # Source-string substring
    [--limit 50] [--offset 0]
```

Returns:
```json
{
  "ok": true,
  "data": {
    "total_matched": 132,
    "returned": 50,
    "offset": 0,
    "entries": [
      {
        "row_id": "r_4f3a...",         // stable handle for chain ops
        "formid": "0x000A2B1C",
        "edid": "SomeEditorID",
        "signature": "WEAP",
        "field": "FULL",
        "index": 0,
        "index_max": 0,
        "source": "Iron Sword",
        "dest": null,
        "status": "untranslated",
        "list_index": 0
      },
      ...
    ]
  }
}
```

#### `xtl inspect entry <project>`

One of three identification modes (mutually exclusive):

```
xtl inspect entry <project>
    (--edid <id> [--signature WEAP] [--field FULL] [--index 0])
    | (--formid <hex> [--signature WEAP] [--field FULL] [--index 0])
    | (--row-id <r_...>)
```

When `--edid` is used without `--signature`/`--field`, returns ALL entries matching that EditorID. Otherwise narrows.

When `--row-id` is used, returns exactly that row.

Returns full entry detail including parent_context if dialog/quest.

#### `xtl inspect orphans <project>`

Lists entries with `oldData` status.

### 3.3 Edit (Mode B writes)

#### `xtl edit entry <project>`

```
xtl edit entry <project>
    (--row-id <r_...> | --edid <id> --signature WEAP --field FULL [--index N] | --formid <hex> --signature WEAP --field FULL [--index N])
    --translation "..."                # Required
    [--status translated|partial|locked]  # Default: translated
    [--source-from "..."]              # Optional: pin which source string this translation applies to (for safety against rescan racing)
```

Returns confirmation with the persisted row.

#### `xtl edit bulk <project>`

```
xtl edit bulk <project>
    --jsonl <path>
```

JSONL format (one row per line):
```json
{"row_id": "r_4f3a...", "translation": "铁剑", "status": "translated"}
{"row_id": "r_5b8c...", "translation": "钢剑", "status": "translated"}
{"edid": "SomeID", "signature": "ARMO", "field": "FULL", "translation": "..."}
```

Returns per-row results array (some may have failed).

#### `xtl edit status <project>`

```
xtl edit status <project>
    (--row-id <r_...> | --edid ... --signature ... --field ...)
    --status untranslated|partial|translated|locked
```

Changes status without touching translation text. Useful for promoting `partial` to `translated` after manual review.

#### `xtl edit revert <project>`

```
xtl edit revert <project>
    (--row-id <r_...> | --edid ... --signature ... --field ...)
```

Clears `dest`, sets status to `untranslated`.

### 3.4 Batch (Mode A)

#### `xtl batch plan <project>`

```
xtl batch plan <project>
    [--signature WEAP,ARMO,...]        # Filter scope; default: all untranslated
    [--field FULL,DESC,...]
    [--status untranslated|partial]    # Default: untranslated
    --register dialogue|ui_label|item_name|item_desc|book_prose|system_message|mcm_setting
    --game-lore "..."                  # Required slot
    --mod-name "..."                   # Required slot
    --mod-theme "..."                  # Required slot
    --style "..."                      # Required slot
    [--extra-context "..."]            # Optional slot
    [--mod-context-file <path>]        # Alternative: TOML/YAML with name/theme/lore-summary slots
    [--prompt-template <name>]
    [--batch-size 40]                  # Default depends on length tier
    [--concurrency 4]                  # Default per profile
    [--profile <name>]                 # Override project's active profile
```

Returns full BatchPlan including:
- plan_id
- batch_count
- total_items
- est_input_tokens / est_output_tokens
- est_cost_usd
- sample_system_prompt (full text of the first batch's system prompt for agent/user preview)

#### `xtl batch run <project>`

```
xtl batch run <project>
    --plan <plan_id>                   # Use prior plan
    OR all-the-flags-from-batch-plan   # Plan-and-run inline (uses same args as plan)
    [--confirm]                        # When using plan-inline mode, suppress GUI prompt-preview popup
```

Returns immediately:
```json
{
  "ok": true,
  "data": {
    "run_id": "rn_8af3...",
    "batches_dispatched": 8,
    "concurrency": 4,
    "preview_status": "skipped|approved|approve_all_remaining"
  }
}
```

Long-running work proceeds in background. Agent polls `xtl batch status`.

#### `xtl batch status <run_id>`

Returns per-batch state for the run:

```json
{
  "ok": true,
  "data": {
    "run_id": "rn_8af3...",
    "status": "running|complete|cancelled|failed",
    "batches_total": 8,
    "batches_done": 5,
    "batches_in_flight": 2,
    "batches_pending": 1,
    "items_translated": 184,
    "items_total": 320,
    "items_manual_review": 3,
    "cost_so_far_usd": 0.42,
    "cost_exact": false,
    "started_at": "...",
    "elapsed_seconds": 73,
    "batches": [
      {
        "batch_id": "b_1...",
        "status": "complete",
        "items": 40,
        "retries": 0,
        "tokens_in": 1200,
        "tokens_out": 1450,
        "cost_usd": 0.06
      },
      ...
    ]
  }
}
```

#### `xtl batch cancel <run_id>`

```
xtl batch cancel <run_id>
    [--client <n>]                     # Cancel single client; default cancels all in-flight
```

Returns:
```json
{
  "ok": true,
  "data": {
    "run_id": "rn_8af3...",
    "client": null,                    // or specific n
    "cancelled_at": "...",
    "batches_cancelled": 2,
    "items_committed_estimate": 32,
    "cost_committed_estimate_usd": 0.03,
    "cost_status": "estimated",
    "note": "Provider may bill for tokens consumed before client-side abort."
  }
}
```

#### `xtl batch logs <run_id>`

```
xtl batch logs <run_id>
    [--client <n>]
    [--follow]                         # Tail
    [--level info|warn|error]
```

### 3.5 Profile

#### `xtl profile add`

```
xtl profile add <name>
    --sdk openai|anthropic|gemini|openai-compat
    --base-url <url>                   # Required for openai-compat
    --model <model-id>                 # Required
    --api-key-env <VARNAME>            # Required; references env var name, NOT key value
    [--max-concurrency 4]
    [--rate-limit-rpm 500]
    [--rate-limit-tpm 200000]
    [--cost-cap-usd 5.00]
    [--require-parameters]             # OpenRouter only: enforce structured-output capability
    [--extra-header KEY=VALUE]         # Can be repeated, e.g. OpenRouter HTTP-Referer
```

Agent CANNOT pass `--api-key <value>`. That field is rejected. Agent's job ends at registering the env var reference and telling the user to populate `profiles/.env`.

#### `xtl profile list`

Returns array of profiles with masked key state (`"BGS_TRANSLATOR_KEY_OPENAI: [loaded]"` or `"[not set]"`).

#### `xtl profile show <name>`

Single profile detail. Key always masked.

#### `xtl profile edit <name>`

Modify existing profile. Same args as `add`. Cannot mutate key value.

#### `xtl profile activate <name>`

Set as global default for new projects.

#### `xtl profile probe <name>`

Sends a tiny test request to probe capability:

```json
{
  "ok": true,
  "data": {
    "profile": "openai-prod",
    "reachable": true,
    "structured_output_supported": true,
    "structured_output_mode": "json_schema_strict",
    "rate_limit_headers_observed": true,
    "rate_limit_suggested_rpm": 500,
    "cancellation_clean": true,
    "ping_ms": 124,
    "cost_for_probe_usd": 0.0001
  }
}
```

### 3.6 Validate

#### `xtl validate project <name>`

Runs all gates across the project memory. Returns per-entry pass/fail summary.

#### `xtl validate sst <path>`

Reads an SST file and round-trips it (parse → re-emit → bytewise diff). Useful for verifying our writer against a known-good reference. Returns diff summary.

### 3.7 Config

#### `xtl config show`

Returns full global settings TOML as JSON.

#### `xtl config set <key> <value>`

Set a global setting. Examples:
```
xtl config set ui_language zh-cn
xtl config set ui_theme amber
xtl config set default_template my_template
xtl config set sst_version SSU9
```

### 3.8 GUI

#### `xtl gui`

```
xtl gui
    [--project <name>]                 # Open with project preselected
    [--theme amber|green|mono]
    [--lang en|zh-cn]
```

Launches Tk control panel. Blocks until GUI is closed. See `07-tk-control-panel.md`.

### 3.9 Version

#### `xtl version`

```
xtl version
```

Returns:
```json
{
  "ok": true,
  "data": {
    "tool_version": "1.0.0",
    "sst_emit_version": "SSU9",
    "sst_read_versions": ["SSU2", "SSU3", "SSU4", "SSU5", "SSU6", "SSU7", "SSU8", "SSU9"],
    "xtranslator_recommended_min": "1.6.0",
    "python_version": "3.12.4",
    "supported_games": ["SkyrimLE", "SkyrimSE", ...]
  }
}
```

---

## 4. Mode A walkthrough (agent perspective)

```bash
# 1. Set up project
xtl project init adwryos-zhcn \
    --source-plugin /path/to/adwryos.esm \
    --game Starfield \
    --source-lang en --target-lang zh-cn \
    --profile openrouter-claude

# 2. See what's there
xtl inspect signatures adwryos-zhcn
# Agent decides to start with weapon names: WEAP+FULL (78 entries, short tier)

# 3. Plan a batch
xtl batch plan adwryos-zhcn \
    --signature WEAP --field FULL \
    --register item_name \
    --game-lore "Starfield (Bethesda 2023 sci-fi RPG, Settled Systems setting)" \
    --mod-name "Adwryo's CC Spaceship Pack" \
    --mod-theme "Adds player-craftable spaceship modules with engineering vocabulary" \
    --style "tone: technical-pragmatic, register: spacefaring engineer" \
    --batch-size 40 \
    --concurrency 4
# Returns plan_id + full sample prompt

# 4. (Optional) User approves prompt via Tk panel if "always preview" is on
# Otherwise:

# 5. Run
xtl batch run adwryos-zhcn --plan plan_xyz123 --confirm
# Returns run_id immediately

# 6. Poll
xtl batch status rn_8af3...
# Or watch GUI Batches tab

# 7. When done, repeat for other signatures
xtl batch plan adwryos-zhcn --signature ARMO --field FULL ...
xtl batch run ...

# 8. Validate and export
xtl validate project adwryos-zhcn
xtl project export adwryos-zhcn --format sst
# Returns 9 SST paths (Starfield dummy-fill default)
```

---

## 5. Mode B walkthrough (agent perspective)

```bash
# 1. Find an entry user mentioned by EditorID
xtl inspect entries adwryos-zhcn --edid-contains "FuelTank" --limit 10
# Returns several rows; agent picks the right one by source text

# 2. Get detail
xtl inspect entry adwryos-zhcn --row-id r_4f3a...
# Returns full unit including parent_context

# 3. Edit (agent provides translation from its own knowledge or chat conversation)
xtl edit entry adwryos-zhcn --row-id r_4f3a... \
    --translation "聚变燃料舱" --status translated

# 4. Bulk fix: agent prepared a JSONL of 15 corrections
xtl edit bulk adwryos-zhcn --jsonl /tmp/fixes.jsonl

# 5. Re-export
xtl project export adwryos-zhcn --format sst
```
