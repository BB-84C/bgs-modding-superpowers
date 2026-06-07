# 04 — AI Pipeline

The pipeline has six explicit stages plus a cross-cutting retry layer:

```
  extract → mask → batch → translate → unmask → validate → (write SST in stage 7 per 03-sst-output.md)
                                ↓                  ↓
                             (cancel)        (retry on soft fail)
```

Each stage owns one bounded transformation. Data flows as immutable dataclasses passed between stages.

---

## Stage 1: extract

**Input**: a project with one source plugin.

**Process**:
1. Open plugin file (lazy mmap if >100 MB, sequential read otherwise)
2. Parse via `parsers.tes3.walk()` (Morrowind only) or `parsers.tes4_family.walk()` (all other games)
3. For each record, enumerate `cpTranslate`-flagged subrecord fields per the per-game schema in `parsers.schemas.<game>`
4. For each field instance (including multi-value subrecord items), produce a `TranslationUnit`

**`TranslationUnit` dataclass**:

```python
@dataclass(frozen=True)
class TranslationUnit:
    plugin: str                 # source plugin filename, e.g. "adwryos.esm"
    formid: int                 # 32-bit FormID as stored in the record
    formid_sanitized: int       # high-byte cleared (formid & 0x00FFFFFF), per xTranslator hash convention
    edid: str | None            # EditorID if record has one; None for INFO:NAM1 etc.
    signature: str              # 4-char record sig, e.g. "WEAP"
    field: str                  # 4-char subrecord sig, e.g. "FULL"
    index: int                  # sub-index within multi-value subrecord, 0 if not applicable
    index_max: int              # total count of sub-items, 0 if not applicable
    source: str                 # decoded source string (per game/locale primary encoding)
    list_index: int             # 0=STRINGS, 1=DLSTRINGS, 2=ILSTRINGS (per cpTranslate routing)
    strid: int                  # Bethesda localized string ID if plugin has TES4 Localized flag set, else 0
    rhash: int                  # stringHash(edid) or stringHash('[xxxxxxxx]') per xTranslator convention
    parent_context: ParentContext | None
```

**`ParentContext` for dialogue/quest records**:

```python
@dataclass(frozen=True)
class ParentContext:
    parent_signature: str       # "DIAL", "QUST"
    parent_formid: int
    parent_edid: str | None
    parent_full: str | None     # e.g., quest name, dialog topic text
    summary: str                # short freeform summary the batcher injects into prompt
```

**Output**: full list of `TranslationUnit` cached to `projects/<name>/sources/<plugin>.cache.bin`. The cache is keyed by `(plugin_sha256, parser_version)`; re-extracts hit the cache when nothing changed.

**Edge cases**:
- Records where the field is missing or empty → not emitted as units (nothing to translate)
- Records where the field is a pure format-only string (e.g., `"%d"`) → emitted with `lockedTrans` precomputed; LLM is skipped in stage 4
- Records where the plugin has TES4 Localized flag set → the field value on disk is a `strid` pointing into `.STRINGS / .DLSTRINGS / .ILSTRINGS`; the extractor reads the actual string from those sidecar files

---

## Stage 2: mask

**Input**: a `TranslationUnit`.

**Output**: a `MaskedUnit`:

```python
@dataclass(frozen=True)
class MaskedUnit:
    unit: TranslationUnit
    source_masked: str                       # what the LLM will see
    mask_map: dict[str, MaskToken]           # for unmask
    byte_budget: int                         # max bytes for dest (default 65520; smaller for certain fields)
    skip_llm: bool                           # True if entire source is protected/locked; LLM skipped
```

**`MaskToken`**:

```python
@dataclass(frozen=True)
class MaskToken:
    placeholder: str                         # "{{P0}}", "{{P1}}", ...
    original: str                            # original text masked
    kind: str                                # see table below
    must_appear_count: int                   # required occurrences in LLM output
    position_locked: bool                    # whether the order relative to other masks matters
    paired_with: str | None                  # placeholder name of matching open/close
```

**Mask categories** (scanned in priority order; first match wins per character span):

| Kind | Pattern | Example | `must_appear_count` | `position_locked` | Paired |
|---|---|---|---|---|---|
| `format_printf` | `%[-+0-9.# ]*[sdiuoxXeEfgG%]` | `%s`, `%.2f`, `%1$s` | 1 | true | no |
| `format_brace_named` | `\{[A-Za-z_][A-Za-z0-9_]*\}` | `{name}`, `{count}` | 1 | true | no |
| `format_brace_indexed` | `\{\d+\}` | `{0}`, `{1}` | 1 | true | no |
| `alias_substitution` | `<Alias[.\w]*=[\w]+>` | `<Alias=PlayerRef>` | 1 | false | no |
| `global_substitution` | `<(Global\|spell\|GameSetting)\.[\w]+>` | `<Global.PlayerLevel>` | 1 | false | no |
| `tag_open_font` | `<font[^>]*>` | `<font color='#FF0000'>` | 1 | true | yes (`tag_close_font`) |
| `tag_close_font` | `</font>` | `</font>` | 1 | true | yes (`tag_open_font`) |
| `newline_structural` | `\r?\n` | `\n` | count-preserving (paragraph reorder allowed) | false | no |
| `mcm_key_prefix` | `^\$[A-Za-z_][\w]*\s` | `$Token text` | extracted out of LLM scope entirely | n/a | no |

**Special handling**:

- **Pure-format strings** (regex matches every character): set `skip_llm=True`, `dest=source` verbatim, status `lockedTrans`. No LLM call.
- **`$Token`-prefix MCM strings**: the `$Token\t` prefix is stripped from `source_masked`. Only the value-side text is sent to LLM. On unmask, the original `$Token\t` is prepended. Source patterns: `$Foo`, `$Foo\tHello World`. Both supported.
- **Empty / whitespace-only / pure punctuation strings**: skip LLM, copy source to dest.
- **Strings entirely matching one of the built-in heuristic skip rules** (see below): `lockedTrans`, skip LLM.

**Built-in heuristic skip rules** (port from xTranslator `TESVT_Const.pas:lRulesNoTransListInDefault`):

```regex
^\w{3,}_\w*$                       # snake_case identifiers
^\w+[A-Z]+[_a-z\d]+[A-Z]+\w+$     # CamelCaseIDs
^\R+$                              # only line breaks
^.{1,2}$                           # 1-2 chars total
^(\W|\d|\.)*$                      # only punctuation/digits
^[\d%\.\\\+\-:]+$                  # only numeric formatting
^\w*\\\w*                          # backslash-containing (paths, internal refs)
```

Strings matching any of these regexes default to `lockedTrans`. Users/agents can override per-record by adding a glossary entry in the `do_not_translate` scope (which behaves additively — heuristics + explicit DNT both apply).

---

## Stage 3: batch (plan)

**Input**: a set of `MaskedUnit`s (those with `skip_llm=False`).

**Process**: group into batches by composite key. Within a group, items are packed into batches up to `batch_size`.

**Group key**:

```
(target_lang, register, signature, parent_context_group, length_tier, glossary_subset_hash)
```

Where:
- `register` ∈ {`dialogue`, `ui_label`, `item_name`, `item_desc`, `book_prose`, `system_message`, `mcm_setting`}. Agent specifies via `--register`.
- `parent_context_group`: for INFO/DIAL → parent DIAL FormID; everything else → null.
- `length_tier` ∈ {`short` (<100 bytes), `medium` (100-500), `long` (>500)}. Long strings get smaller batches due to output-token budget pressure.
- `glossary_subset_hash`: SHA-1 of the sorted list of glossary entry IDs whose source aliases match any string in the batch. Items in the same batch share the same glossary system-prompt section.

**`BatchPlan` output**:

```python
@dataclass(frozen=True)
class BatchPlan:
    plan_id: str                             # uuid4, persisted under batches/<run_id>/
    project: str
    profile_name: str
    target_lang: str
    register: str
    batches: list[Batch]
    total_items: int
    est_input_tokens: int                    # sum across all batches
    est_output_tokens: int                   # ~1.3x input by default; refined per provider over time
    est_cost_usd: float
    sample_system_prompt: str                # rendered for batches[0], shown to agent/user for preview

@dataclass(frozen=True)
class Batch:
    batch_id: str                            # uuid4
    items: list[MaskedUnit]
    parent_context_summary: str | None
    glossary_subset: list[GlossaryEntry]
    do_not_translate: list[str]
```

**Sizing defaults**:
- short tier: batch_size = 40
- medium tier: batch_size = 20
- long tier: batch_size = 10
- Agent overrides via `--batch-size N`

**Cost estimation**: see `10-cost-rate-cancel.md` §3.

---

## Stage 4: translate

This is where the work actually leaves the machine. Three sub-concerns: prompt assembly, dispatch, structured-output schema.

### 4.1 System prompt template

Canonical template (Chinese register; English target is symmetric):

```
你是 {game_lore_world} 的本地化译者。

游戏世界：{game_context_lore_summary}
mod：{mod_context_name} —— {mod_context_theme}
{parent_context_summary_if_present}

风格要求：
{style_directives}

补充上下文：
{ad_hoc_context_if_present}

术语表（必须严格遵循）：
{glossary_subset_rendered}

禁止翻译（保持原文）：
{do_not_translate_list}

注意：占位符 {{P0}}, {{P1}}, ... 不要翻译、不要删除、不要增加。
返回 JSON 格式 {"I1": "译文", "I2": "译文", ...}
```

Slots use Python `string.Template` `${slot}` syntax (the literal `{{P0}}` in the template is escaped as `$${{P0}}` internally). Tool validates required slots are present at template load time.

### 4.2 Slot sources

| Slot | Source | Required | How to provide |
|---|---|---|---|
| `${game_lore_world}` | **Agent-provided** | yes | `xtl batch plan --game-lore "..."` or via `--mod-context-file <path>` |
| `${game_context_lore_summary}` | **Agent-provided** | yes | same channels as above |
| `${mod_context_name}` | **Agent-provided** | yes | `--mod-name "..."` |
| `${mod_context_theme}` | **Agent-provided** | yes | `--mod-theme "..."` |
| `${parent_context_summary_if_present}` | **Batcher-derived** | auto, may be empty | For INFO/DIAL, batcher writes "This is a dialog response in quest 'The Forgotten Vault'." When absent, the entire line is omitted (not left blank) |
| `${style_directives}` | **Agent-provided** | yes | `--style "..."` (multi-line accepted) |
| `${ad_hoc_context_if_present}` | **Agent-provided** | optional | `--extra-context "..."` or `--extra-context-file <path>`; the "补充上下文：" line is omitted entirely when empty |
| `${glossary_subset_rendered}` | **Auto from KB** | auto | Filtered to entries whose source aliases match strings in this batch. Rendered as `源 → 译文 (类别)` lines |
| `${do_not_translate_list}` | **Auto from KB + heuristics** | auto | Union of `do_not_translate` scope glossary + heuristic matches in this batch |

**Why agent-provided game lore and mod context** (not KB auto-injected):
- Agent's chat context typically has fuller, more current information about THIS specific mod than the KB would
- Different mods need different lore framing: a Skyrim political quest mod and a Skyrim weapon pack need totally different "world" descriptions in the prompt
- KB auto-injection would risk over-stuffing the prompt with irrelevant lore for narrow-scope mods
- Glossary lookup stays auto because it is mechanical (term-level matching), narrow (only hits matter), and benefits from the KB's curated canonical translations

### 4.3 Custom prompt templates

Path: `~/.bgs-modding-superpowers/translator/config/prompt-templates/<name>.md`

Default template ships as `default.md` containing the exact text above.

Override mechanism:
- Global default: `xtl config set default_template <name>`
- Per-project: `project.toml` → `[translation] prompt_template = "<name>"`
- Per-batch: `xtl batch plan ... --prompt-template <name>`

Tool validates at template load:
- All required slots are referenced
- All referenced slots are in the allowed set
- No syntax errors

### 4.4 LLM dispatch — four `sdk_kind`s

| `sdk_kind` | Library | API call | Structured output mechanism | Notes |
|---|---|---|---|---|
| `openai` | `openai` | `client.responses.create(...)` — Responses API | `text.format` with `json_schema` strict | OpenAI proper |
| `anthropic` | `anthropic` | `client.messages.create(...)` — Messages API | Tool use with `strict: true` and explicit `input_schema` | Native Anthropic, prompt caching supported |
| `gemini` | `google-genai` | `client.models.generate_content(...)` | `response_schema` + `response_mime_type: "application/json"` | Native Gemini SDK |
| `openai-compat` | `openai` SDK with `base_url` override | `client.chat.completions.create(...)` — chat completions, **honest** | DeepSeek: `response_format={"type": "json_object"}` + Pydantic validation; OpenRouter: `response_format={"type": "json_schema", ...}` + `provider: {"require_parameters": true}` | DeepSeek, OpenRouter, Ollama, vLLM, local proxies. No fake Response wrapping. |

**Why `openai-compat` is its own kind** (and not lumped under `openai`):
- These endpoints only support chat completions, not Responses
- Their `response_format` capabilities vary (DeepSeek: `json_object` only; OpenRouter: `json_schema` with provider-routing requirement)
- Their rate-limit headers and usage-reporting shapes vary
- Pretending they expose a Responses API is dishonest and hides real provider quirks from the audit trail

**Internal `LLMResponse` normalization**:

```python
@dataclass(frozen=True)
class LLMResponse:
    items: dict[str, str]                    # batch item_id → translated text
    usage: TokenUsage                        # input/output/cached/total tokens
    cost_usd: float | None                   # None = not yet computed
    cost_exact: bool                         # True only for providers that return cost in response (OpenRouter)
    rate_limit_observed: RateLimit | None
    request_id: str | None
    raw_response_path: Path                  # audit trail file
    via: Literal["responses", "messages", "generate_content", "chat_completions"]
```

The `via` field is the honest record of which wire API was used. Audits can see exactly.

### 4.5 Structured output schema (Pydantic)

```python
class BatchTranslationOutput(BaseModel):
    """LLM is required to return this exact shape; extra keys forbidden."""
    items: dict[str, str]  # key = batch-local item_id "I1", "I2", ..., value = translated string

    model_config = ConfigDict(extra="forbid")
```

Each `sdk_kind` adapter takes this Pydantic model and produces the appropriate provider-specific schema for the request.

### 4.6 Concurrency and cancellation

Per-profile `max_concurrency` controls parallelism via `asyncio.Semaphore`. Token bucket (per `10-cost-rate-cancel.md` §2) further throttles dispatch.

Cancellation semantics:
- `xtl batch cancel <run_id>` → cancel all in-flight batches in this run
- `xtl batch cancel <run_id> --client <n>` → cancel one client task; others continue
- GUI Batches tab [Cancel] button per row → same semantics

Per Lane 2 research, cancelling the asyncio task closes the local HTTP request via httpx; this does **not** guarantee the provider stops billing. UI and `LLMResponse.cost_usd` label cost-on-cancel as estimated and may have been billed for tokens already consumed before abort. The `xtl batch cancel` envelope explicitly carries this caveat.

---

## Stage 5: unmask

**Input**: `LLMResponse.items[item_id]` (translated string) + corresponding `MaskedUnit.mask_map`.

**Process**:
1. For each `(placeholder, MaskToken)` in `mask_map`:
   - Find all occurrences of `placeholder` in LLM output
   - Replace with `original`
2. If the original unit had `mcm_key_prefix` kind, prepend the stored `$Token\t` to the result
3. Normalize newlines back to the source's convention (`\r\n` vs `\n` consistency)

**Output**: `TranslatedUnit`:

```python
@dataclass(frozen=True)
class TranslatedUnit:
    unit: TranslationUnit
    dest: str
    via_llm: bool                            # False for skip/locked/identity passthroughs
    profile_used: str
    sdk_via: str                             # "responses" | "messages" | "generate_content" | "chat_completions"
    cost_estimate_usd: float
    cost_exact: bool
    retry_count: int                         # 0 if first attempt succeeded
```

---

## Stage 6: validate

Gates run in this order; first failure determines result and routing.

| # | Gate | Check | Failure routes to |
|---|---|---|---|
| 1 | **Mask completeness** | Every `must_appear_count >= 1` placeholder in `mask_map` appears at least that many times in `dest` | retry (corrective) |
| 2 | **Pair nesting** | All `tag_open`/`tag_close` pairs are matched and ordered consistently | retry (corrective) |
| 3 | **No hallucinated placeholders** | No `{{Pn}}` pattern in `dest` that wasn't in `mask_map` | retry (corrective) |
| 4 | **Byte budget** | UTF-8-encoded length(`dest`) ≤ `byte_budget` | retry (request shorter) |
| 5 | **Encoding feasibility** | All chars in `dest` are encodable in target locale's primary encoding OR documented fallback | flag for human review (no retry) |
| 6 | **Do-not-translate intact** | All `do_not_translate` glossary terms that appeared in `source` also appear verbatim in `dest` | retry (corrective) |
| 7 | **MCM key intact** | If source began with `$Token\t...`, `dest` begins with the same `$Token\t...` | retry (corrective) |
| 8 | **Length sanity** | `len(dest) / len(source)` ∈ `[0.3, 3.0]` after target-language expansion factor | soft warning, not blocking |

**Soft warnings** (logged but never blocking):
- Glossary preferred-form deviation (LLM used a synonym translation when glossary had a different canonical)
- Length-sanity (gate 8)

---

## Retry layer

When a hard gate (1, 2, 3, 4, 6, 7) fails:

1. Build a corrective addendum to the user message (system prompt unchanged):

```
The previous attempt failed validation on these items. Please correct only the listed items and resend the FULL JSON object:

- Item I3: placeholder {{P0}} (which represents "%d") must appear exactly once but was missing.
- Item I5: <font> tag was opened but not closed.

Original items follow. Please return the full corrected JSON.
```

2. Resend with same system prompt + addendum + original items.
3. Max 2 retries per batch (configurable per profile via `max_retries`).
4. After 2 failed retries, items go to manual-review queue with status `incompleteTrans`. The successful items in the same batch are kept.

The retry layer reuses the same LLM client task, so cancellation cancels the retry too.

---

## Stage 7: write SST (handed off to `03-sst-output.md`)

After validate (or after manual-review placement), each `TranslatedUnit` writes to `projects/<name>/memory/memory.sqlite` with status:
- `translated` — full validation pass
- `incompleteTrans` — manual-review queue (retry budget exhausted)
- `lockedTrans` — pre-skip from mask stage

The export step (`xtl project export --format sst`) reads `memory.sqlite` and emits `.sst` per `03-sst-output.md` rules.

---

## Encoding-feasibility table (gate 5)

Per-game per-locale encoding chain. Decoding tries primary first, falls back. Encoding (for our purposes) checks whether each char in `dest` can be represented in ANY encoding in the list — if not, gate 5 flags.

```python
ENCODING_FALLBACK: dict[GameCode, dict[LangCode, list[str]]] = {
    "SkyrimSE": {
        "en":    ["utf-8", "windows-1252"],
        "fr":    ["utf-8", "windows-1252"],
        "de":    ["utf-8", "windows-1252"],
        "it":    ["utf-8", "windows-1252"],
        "es":    ["utf-8", "windows-1252"],
        "pl":    ["utf-8", "cp1250-custom"],
        "ru":    ["utf-8", "windows-1251"],
        "cs":    ["cp1250-custom"],
        "ja":    ["utf-8"],
        "zh-cn": ["utf-8"],
    },
    "Fallout4": {
        # similar shape; codepage.txt may dictate locales differently
    },
    "Starfield": {
        # all locales documented to UTF-8 primary; per-locale fallback per CK Audit Tool guidance
    },
    "Morrowind": {
        # Inline TES3 strings; encoding is per-locale Windows ANSI typically
    },
    # ... continued in code, not duplicated here
}
```

The full table lives in code under `pipeline/encoding_table.py` and is the authoritative source. This document records the **shape** of the contract; the **values** are code.

---

## Audit trail

Every batch run preserves under `projects/<name>/batches/<run-id>/`:

```
batches/<run-id>/
├── plan.json                  # the full BatchPlan
├── system-prompt.md           # exact rendered system prompt(s); one per unique prompt
├── responses/
│   ├── <batch-id>.raw.json    # raw LLM response body
│   └── <batch-id>.normalized.json  # LLMResponse dataclass serialized
├── retries/
│   └── <batch-id>.attempt-N.json  # per-retry attempts
├── results.json               # final list of TranslatedUnit
├── validator-failures.jsonl   # one line per failed gate, with item_id + reason
└── status.toml                # final state: total/succeeded/retried/manual_review/cancelled/cost
```

Run dirs are never deleted by the tool. User deletes manually when they want to clean up. This implements the `30-operational-continuity-and-state-hygiene.md` principle that every implementation round leaves traceable evidence.
