# 08 — Persistence and Paths

## Unified root path

The user has pre-approved touching `bgs-kb`'s storage location to consolidate everything under a single user-data root that works identically on all OSes:

```
~/.bgs-modding-superpowers/
```

`~` resolves correctly on all platforms:
- Windows: `C:\Users\<name>\.bgs-modding-superpowers\`
- Linux: `$HOME/.bgs-modding-superpowers/`
- macOS: `$HOME/.bgs-modding-superpowers/`

Override via env var: `BGS_MODDING_SUPERPOWERS_HOME=/some/other/path`.

---

## 1. Full directory tree

```
~/.bgs-modding-superpowers/
├── kb/                                       # bgs-kb cache (migrated from old location)
│   ├── manifest-index.json
│   ├── packs/
│   │   ├── bgs-kb-core/
│   │   │   ├── manifest.toml
│   │   │   └── store.sqlite
│   │   ├── bgs-kb-skyrim/
│   │   │   ├── manifest.toml
│   │   │   └── store.sqlite
│   │   ├── bgs-kb-fallout4/
│   │   │   ├── manifest.toml
│   │   │   └── store.sqlite
│   │   ├── bgs-kb-fallout3-fnv/
│   │   │   ├── manifest.toml
│   │   │   └── store.sqlite
│   │   ├── bgs-kb-l10n-skyrim-en-zhcn/      # NEW: translation glossary packs
│   │   │   ├── manifest.toml
│   │   │   └── store.sqlite
│   │   └── ... etc
│   └── user-packs/                           # $BGS_KB_USER_PACKS overlay
│       └── translator-overrides-en-zhcn/
│           ├── manifest.toml
│           └── store.sqlite
├── translator/
│   ├── projects/
│   │   ├── adwryos-zhcn/
│   │   │   ├── project.toml                  # Project metadata + settings
│   │   │   ├── sources/
│   │   │   │   ├── adwryos.esm.cache.bin     # Parsed TranslationUnit list
│   │   │   │   └── adwryos.esm.cache.toml    # Cache metadata (hash, parser_version)
│   │   │   ├── memory/
│   │   │   │   └── memory.sqlite             # Translation memory (per-project)
│   │   │   ├── batches/
│   │   │   │   └── <run-id>/
│   │   │   │       ├── plan.json
│   │   │   │       ├── system-prompt.md
│   │   │   │       ├── responses/<batch-id>.raw.json
│   │   │   │       ├── responses/<batch-id>.normalized.json
│   │   │   │       ├── retries/<batch-id>.attempt-N.json
│   │   │   │       ├── results.json
│   │   │   │       ├── validator-failures.jsonl
│   │   │   │       └── status.toml
│   │   │   └── exports/
│   │   │       ├── adwryos_english_chinese.sst
│   │   │       ├── adwryos_english_english.sst  # Starfield dummy-fill
│   │   │       ├── adwryos_english_french.sst   # ...
│   │   │       └── adwryos_english_chinese.xml  # optional sidecar
│   │   └── _archived/
│   │       └── old-project-name-2026-05-22/
│   ├── profiles/
│   │   ├── profiles.toml                     # Provider profiles (no keys)
│   │   ├── .env                              # API keys (0600, gitignored)
│   │   └── .probe-cache.json                 # Cached probe results, 24h TTL
│   ├── config/
│   │   ├── settings.toml                     # Global UI + behavior settings
│   │   ├── pricing.toml                      # Per-model cost table
│   │   └── prompt-templates/
│   │       ├── default.md                    # Default system prompt template
│   │       └── <custom>.md
│   └── logs/
│       ├── 2026-06-06.log
│       └── 2026-06-07.log
└── tools/                                    # One-off scripts (not part of normal workflow)
    ├── import-xtranslator-xml.py
    └── import-xtranslator-sst.py
```

---

## 2. File format conventions

| File | Format | Purpose | Editable by |
|---|---|---|---|
| `project.toml` | TOML | Project metadata + per-project settings | User + agent + tool |
| `memory.sqlite` | SQLite 3 | Translation memory, schema versioned | Tool only (concurrent access via WAL) |
| `*.cache.bin` | Pickle (Python) | Parsed TranslationUnit list, fast reload | Tool only (regenerable) |
| `*.cache.toml` | TOML | Cache invalidation metadata | Tool only |
| `plan.json` | JSON | BatchPlan as serialized dataclass | Tool only (audit trail) |
| `system-prompt.md` | Markdown | Rendered system prompt for a batch | Tool writes; user reads |
| `responses/*.raw.json` | JSON | Raw LLM response body | Tool only |
| `validator-failures.jsonl` | JSON Lines | Per-failure records | Tool only |
| `status.toml` | TOML | Final batch run state | Tool only |
| `profiles.toml` | TOML | Provider profiles | User + agent + tool |
| `.env` | dotenv | API keys | User only (GUI writes, agent does not read) |
| `settings.toml` | TOML | Global UI settings | User + tool |
| `pricing.toml` | TOML | Per-model price table | User + tool |
| `prompt-templates/*.md` | Markdown w/ `$slot` placeholders | System prompt templates | User + agent + tool |
| `logs/*.log` | JSONL (one event per line) | Application logs | Tool writes; user reads |

### 2.1 `project.toml` schema

```toml
schema_version = 1

[project]
name = "adwryos-zhcn"
created_at = 2026-06-06T12:00:00Z
game = "Starfield"
source_lang = "en"
target_lang = "zh-cn"
source_plugin_path = "/path/to/adwryos.esm"
source_plugin_sha256 = "a3f4..."
parser_version = "1.0.0"

[settings]
active_profile = "openrouter-claude"          # Project-pinned profile; falls back to global active if missing
prompt_template = "default"
starfield_dummy_fill = true                   # Auto-enabled for Starfield projects

[cost]
cap_usd = 10.00
spent_usd_session = 0.42
spent_usd_total = 0.42

[mod_context]                                  # Optional: stored mod context for re-use across batches
name = "Adwryo's CC Spaceship Pack"
theme = "Player-craftable spaceship modules with engineering vocabulary"
extra_context = ""

[style]
directives = """
tone: technical-pragmatic
register: spacefaring engineer
"""
```

The agent can `xtl config set` (per-project variant) to update mod_context and style across the project, avoiding having to pass them on every `xtl batch plan` call.

### 2.2 `memory.sqlite` schema

```sql
CREATE TABLE schema_version (version INTEGER);
INSERT INTO schema_version VALUES (1);

CREATE TABLE units (
    row_id TEXT PRIMARY KEY,             -- "r_<uuid4>"
    plugin TEXT NOT NULL,
    formid INTEGER NOT NULL,
    formid_sanitized INTEGER NOT NULL,
    edid TEXT,                            -- NULL for records without EditorID
    signature TEXT NOT NULL,              -- 4-char
    field TEXT NOT NULL,                  -- 4-char
    index_n INTEGER NOT NULL DEFAULT 0,
    index_max INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,
    list_index INTEGER NOT NULL,          -- 0/1/2
    strid INTEGER NOT NULL DEFAULT 0,
    rhash INTEGER NOT NULL,
    parent_context_json TEXT,             -- serialized ParentContext or NULL
    dest TEXT,                            -- NULL when untranslated
    status TEXT NOT NULL,                 -- 'untranslated' | 'translated' | 'partial' | 'locked' | 'orphan'
    sparams INTEGER NOT NULL,             -- bitset: translated/lockedTrans/incompleteTrans/oldData/...
    via_llm BOOLEAN NOT NULL DEFAULT 0,
    profile_used TEXT,
    sdk_via TEXT,                         -- 'responses'|'messages'|'generate_content'|'chat_completions'
    cost_estimate_usd REAL,
    cost_exact BOOLEAN,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_batch_id TEXT,
    updated_at TEXT NOT NULL              -- ISO 8601
);

CREATE INDEX idx_units_signature ON units(signature, field);
CREATE INDEX idx_units_status ON units(status);
CREATE INDEX idx_units_edid ON units(edid);
CREATE UNIQUE INDEX idx_units_natural ON units(plugin, formid, signature, field, index_n);

CREATE TABLE batches (
    batch_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    profile_snapshot_json TEXT NOT NULL,
    item_count INTEGER NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    status TEXT NOT NULL,                 -- 'queued'|'in-flight'|'complete'|'cancelled'|'failed'
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd REAL,
    cost_exact BOOLEAN,
    retry_count INTEGER DEFAULT 0,
    notes TEXT
);

CREATE INDEX idx_batches_run ON batches(run_id);
CREATE INDEX idx_batches_status ON batches(status);

CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    batches_total INTEGER NOT NULL,
    cost_total_usd REAL,
    cost_exact BOOLEAN
);
```

WAL mode enabled for concurrent CLI + GUI access.

---

## 3. KB cache migration

`bgs-kb` already exists and stores its packs somewhere on disk (the exact prior location depends on user install). This PRD requires the cache to live under `~/.bgs-modding-superpowers/kb/`.

### 3.1 Migration trigger

When `bgs-translator` starts (CLI or GUI), it checks:

```python
def maybe_migrate_kb_cache() -> None:
    new_root = paths.home() / "kb"
    old_root = paths.detect_legacy_bgs_kb_cache()  # Implementation: check various paths used by older bgs-kb versions
    
    if old_root and old_root != new_root and not new_root.exists():
        # User has legacy KB cache that needs migrating
        prompt_user_for_migration(old_root, new_root)
```

### 3.2 Migration UX

CLI:
```
$ xtl version
Legacy bgs-kb cache detected at:
    /home/user/.local/share/bgs-kb-cache/

This tool now expects KB cache at:
    /home/user/.bgs-modding-superpowers/kb/

Migrate now? [Y/n] y

Moving packs/ ... done
Moving manifest-index.json ... done
Creating compatibility symlink at old location ... done

Migration complete. bgs-translator will use the new location.
```

GUI: shows the same prompt as a modal dialog on first launch.

### 3.3 Implementation

```python
def migrate_kb_cache(old_root: Path, new_root: Path) -> None:
    new_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old_root), str(new_root))
    
    # Create symlink/junction at old location for backward compat
    try:
        if os.name == "nt":
            subprocess.run(["mklink", "/J", str(old_root), str(new_root)], shell=True, check=True)
        else:
            old_root.symlink_to(new_root)
    except OSError:
        # Symlink creation failed; warn but continue
        log.warning(f"Could not create compatibility symlink at {old_root}. Older bgs-kb invocations may fail.")
```

### 3.4 bgs-kb-side awareness

The bgs-kb codebase needs to be updated to look at the new path by default. Specifically:
- `bgs_kb_status` MCP tool returns the new path
- `bgs_kb_install_pack` installs to the new path
- `bgs_kb_check_updates` reads from new path

This is a separate work item on the bgs-kb codebase. Tracked in `12-implementation-chunks.md` under "KB-side prep work."

### 3.5 Skip migration

`xtl config set skip_kb_migration true` skips the prompt and uses the old location indefinitely. Not recommended; provided for users who deliberately want to keep old layout.

---

## 4. `pricing.toml` (cost estimation table)

Per-model price data, user-editable. Tool ships defaults; users can update when providers change prices.

```toml
schema_version = 1
updated_at = 2026-06-06

[openai]
"gpt-5-mini" = { input_per_1m = 0.50, output_per_1m = 2.00 }
"gpt-5" = { input_per_1m = 5.00, output_per_1m = 20.00 }
"gpt-4o" = { input_per_1m = 2.50, output_per_1m = 10.00 }
"gpt-4o-mini" = { input_per_1m = 0.15, output_per_1m = 0.60 }

[anthropic]
"claude-opus-4-7" = { input_per_1m = 15.00, output_per_1m = 75.00, cache_read_per_1m = 1.50 }
"claude-sonnet-4-7" = { input_per_1m = 3.00, output_per_1m = 15.00, cache_read_per_1m = 0.30 }

[gemini]
"gemini-2.5-pro" = { input_per_1m = 1.25, output_per_1m = 5.00 }
"gemini-2.5-flash" = { input_per_1m = 0.10, output_per_1m = 0.40 }

[deepseek]
"deepseek-chat" = { input_per_1m = 0.27, output_per_1m = 1.10 }

# OpenRouter: cost is reported per-response, so no entries needed here
# Other openai-compat: user adds entries manually
```

The pricing.toml format is shared and stable; users can sync updates from the project's GitHub `defaults/pricing.toml` whenever providers change prices.

---

## 5. `settings.toml` (global UI + behavior)

```toml
schema_version = 1

[ui]
language = "zh-cn"                    # "en" | "zh-cn"
theme = "amber"                       # "amber" | "green" | "mono"
window_width = 1440
window_height = 900
left_panel_width = 240

[behavior]
default_template = "default"
sst_version = "SSU9"                  # "SSU9" | "SSU8" | etc.; downgrade for older xTranslator installs
skip_kb_migration = false
prompt_preview_required = false       # Per-project override possible
```

CLI `xtl config show` returns this as JSON; `xtl config set` updates.

---

## 6. Cache invalidation

`sources/<plugin>.cache.bin` is invalidated when:
- Plugin SHA256 changes (mod was updated)
- Parser version changes (tool was updated and parser logic changed)
- Per-game schema changed

`sources/<plugin>.cache.toml` records the cache key:

```toml
plugin_sha256 = "a3f4..."
parser_version = "1.0.0"
schema_version = "starfield-1.0.0"
extracted_units = 642
extracted_at = 2026-06-06T12:34:56Z
```

On `xtl project rescan`, tool reads .cache.toml, compares against current plugin + parser/schema versions, and:
- If all match: cache hit, fast reload
- If plugin changed: re-extract, then run partial-translation detection logic to mark changed entries as `incompleteTrans`
- If parser/schema changed: re-extract; old entries remain in memory.sqlite by `(formid, signature, field, index_n)` key

---

## 7. Logging

Daily log rotation, kept 30 days.

JSON Lines format, one event per line:

```json
{"ts": "2026-06-06T12:34:56Z", "level": "info", "source": "batch", "run_id": "rn_8af3...", "batch_id": "b_2b4...", "msg": "batch complete", "items": 40, "cost_usd": 0.06, "tokens_in": 1200, "tokens_out": 1450}
```

Log levels: `debug`, `info`, `warn`, `error`.

Log sources: `cli`, `gui`, `parser`, `pipeline`, `validator`, `kb`, `profile-probe`, `cost-tracker`, `rate-tracker`, `sst-write`, `migration`.

CLI flag `--log-level debug` raises verbosity. GUI Logs tab filters live.
