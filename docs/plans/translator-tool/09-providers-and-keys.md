# 09 — Providers and API Keys

## Goals

1. Support OpenAI, Anthropic, Gemini natively via their own modern APIs (Responses / Messages / generate_content)
2. Support DeepSeek, OpenRouter, Ollama, vLLM, and arbitrary user-configured endpoints via OpenAI-compatible chat completions — **honestly**, without fake Response-shape wrapping
3. Isolate API keys from the agent's default access scope (`profiles/.env` separate from `profiles/profiles.toml`)
4. Allow runtime profile switching (next batch uses the new profile; in-flight batches unaffected)
5. Tk GUI is the **write path** for keys; agent registers env-var-references only

---

## 1. The four `sdk_kind`s

| `sdk_kind` | Native SDK | API call | Why this kind exists |
|---|---|---|---|
| `openai` | `openai` Python SDK | `client.responses.create(...)` — Responses API | OpenAI proper, modern API surface |
| `anthropic` | `anthropic` Python SDK | `client.messages.create(...)` — Messages API | Native Claude with prompt caching + tool-use structured output |
| `gemini` | `google-genai` Python SDK | `client.models.generate_content(...)` | Native Gemini with `response_schema` |
| `openai-compat` | `openai` Python SDK with `base_url=...` | `client.chat.completions.create(...)` — chat completions | DeepSeek, OpenRouter, Ollama, vLLM, local proxies. These endpoints **do not** support Responses API. We call chat completions honestly. |

### Why `openai-compat` is a distinct kind

Earlier in design we considered normalizing all four kinds onto a fake unified Responses-shape internal interface. User feedback rejected that: "没办法支持response的就诚实使用chat completion，不额外包装response."

Concrete reasons this is the right call:
- DeepSeek and OpenRouter expose **only** chat completions
- Their `response_format` capabilities differ from Responses' `text.format` strict mode
- Their rate-limit headers and usage-reporting shapes are chat-completions-specific
- Pretending they expose Responses hides real provider quirks from the audit trail
- An agent debugging "why did this fail" needs to see "via=chat_completions", not a misleading "via=responses"

### Internal normalization

All four kinds produce an `LLMResponse` (see `04-ai-pipeline.md` §4.4). The `LLMResponse.via` field records the wire API used:

```python
LLMResponse.via ∈ {"responses", "messages", "generate_content", "chat_completions"}
```

This is an honest record. Audit logs show exactly which wire API delivered the result.

---

## 2. Provider profile data model

File: `~/.bgs-modding-superpowers/translator/profiles/profiles.toml`

This file is **agent-readable** and **agent-writable** (CLI `xtl profile add/edit`). It contains everything **except** API key values.

### 2.1 Schema

```toml
schema_version = 1

[active]
profile = "openrouter-claude"           # Currently-active profile name

[profiles.openai-prod]
sdk_kind        = "openai"
base_url        = "https://api.openai.com/v1"
model           = "gpt-5-mini"
api_key_env     = "BGS_TRANSLATOR_KEY_OPENAI"   # Env var NAME, not value
max_concurrency = 4
rate_limit_rpm  = 500
rate_limit_tpm  = 200000
cost_cap_usd    = 5.00
notes           = "Production OpenAI"
created_at      = 2026-06-06T12:00:00Z

[profiles.anthropic-prod]
sdk_kind        = "anthropic"
base_url        = "https://api.anthropic.com/v1"
model           = "claude-sonnet-4-7"
api_key_env     = "BGS_TRANSLATOR_KEY_ANTHROPIC"
max_concurrency = 3
rate_limit_rpm  = 100
cost_cap_usd    = 10.00
prompt_caching  = true                  # Anthropic-only flag

[profiles.gemini-prod]
sdk_kind        = "gemini"
base_url        = "https://generativelanguage.googleapis.com"
model           = "gemini-2.5-pro"
api_key_env     = "BGS_TRANSLATOR_KEY_GEMINI"
max_concurrency = 4
rate_limit_rpm  = 200
cost_cap_usd    = 5.00

[profiles.deepseek]
sdk_kind        = "openai-compat"
base_url        = "https://api.deepseek.com"
model           = "deepseek-chat"
api_key_env     = "BGS_TRANSLATOR_KEY_DEEPSEEK"
max_concurrency = 8
rate_limit_rpm  = 1000
cost_cap_usd    = 1.00
json_mode       = "json_object"         # DeepSeek-specific: not json_schema strict

[profiles.openrouter-claude]
sdk_kind         = "openai-compat"
base_url         = "https://openrouter.ai/api/v1"
model            = "anthropic/claude-sonnet-4.5"
api_key_env      = "BGS_TRANSLATOR_KEY_OPENROUTER"
max_concurrency  = 3
rate_limit_rpm   = 100
cost_cap_usd     = 10.00
require_parameters = true               # Force routing to providers that support structured output
extra_headers    = { "HTTP-Referer" = "https://github.com/BB-84C/bgs-modding-superpowers", "X-Title" = "bgs-translator" }
```

### 2.2 Schema validation

On load, the tool uses Pydantic v2 to validate. Specific guards:

1. `api_key_env` MUST match `^[A-Z][A-Z0-9_]+$` (a valid env-var name)
2. Any field literally named `api_key`, `apikey`, `key`, `secret`, `token` with a string value → **load error**: "Profile contains what appears to be a literal API key. API keys belong in profiles/.env, referenced by api_key_env."
3. `sdk_kind ∈ {openai, anthropic, gemini, openai-compat}`
4. `base_url` must be valid HTTPS (or `http://localhost:*` for Ollama-style local)
5. For `sdk_kind = openai-compat`, `json_mode` MUST be set to one of `{json_object, json_schema}`

### 2.3 Agent's CLI surface (`xtl profile add/edit`)

The CLI **does not** accept a `--api-key` flag with a value. The CLI accepts only `--api-key-env <VARNAME>`. Attempting to pass `--api-key <value>` produces `error.code = invalid_argument` with message: "API key values are not accepted via CLI. Reference an env var name via --api-key-env."

This is enforced regardless of who runs the CLI (agent or human). It's a structural constraint, not a policy.

---

## 3. The `.env` file

File: `~/.bgs-modding-superpowers/translator/profiles/.env`

This file is the **only** place API key values live. It's loaded via `python-dotenv` and **only** from the LLM dispatch code path.

### 3.1 File contents

```bash
BGS_TRANSLATOR_KEY_OPENAI=sk-...
BGS_TRANSLATOR_KEY_ANTHROPIC=sk-ant-...
BGS_TRANSLATOR_KEY_GEMINI=AIza...
BGS_TRANSLATOR_KEY_DEEPSEEK=sk-...
BGS_TRANSLATOR_KEY_OPENROUTER=sk-or-...
```

### 3.2 File permissions

| Platform | Mode |
|---|---|
| POSIX | 0600 (owner read/write only) |
| Windows | NTFS ACL restricting to current user account |

Permissions are set when the file is first created (by GUI or by user manually) and checked at LLM dispatch time. If permissions are too permissive, the tool refuses to load with `error.code = profile_missing_key` and message: "profiles/.env exists but has world-readable permissions. Run `chmod 600 ...` (POSIX) or restrict via NTFS ACL (Windows)."

### 3.3 Agent access boundary

The agent's `using-bgs-translator` skill explicitly instructs:

> Do NOT read `~/.bgs-modding-superpowers/translator/profiles/.env`. To register a new key, instruct the user to add `<VARNAME>=<value>` themselves via the Tk Profiles tab or by editing `.env` in their text editor.

The skill also instructs the agent to not list directory contents of `profiles/` beyond what's strictly necessary.

This is **defense-in-depth** (the agent can technically still read any file it has filesystem access to). The actual protection is:
1. Structural: the CLI never accepts key values, never echoes them
2. Skill-level: the agent is told not to read .env
3. Audit: any access to .env by tool code goes through one centralized loader function that logs the access

### 3.4 Tool internal access to .env

Only one function loads .env:

```python
# bgs_translator/config/profiles.py
def resolve_api_key(profile: ProviderProfile) -> str:
    """Loads the API key for a profile. ONLY call site for .env access."""
    from dotenv import load_dotenv, dotenv_values
    
    env_path = paths.profiles_dir() / ".env"
    _check_permissions_or_raise(env_path)
    
    values = dotenv_values(env_path)
    key = values.get(profile.api_key_env)
    if not key:
        raise ProfileMissingKeyError(profile.name, profile.api_key_env)
    
    return key
```

Called from `pipeline/clients/*.py` immediately before HTTP dispatch. Never cached longer than the request lifetime. Never logged. Never written to disk.

---

## 4. GUI surface for key management (Tk Profiles tab)

The Tk panel is the **primary write path** for keys. See `07-tk-control-panel.md` §3.5 for full widget detail.

### 4.1 Profile card display

```
┌─ Profile: openrouter-claude ───────────────────────┐
│  SDK kind:       openai-compat                      │
│  Base URL:       https://openrouter.ai/api/v1       │
│  Model:          anthropic/claude-sonnet-4.5        │
│  Concurrency:    3                                  │
│  Rate limit:     100 RPM                            │
│  Cost cap:       $10.00 / $0.42 used                │
│                                                      │
│  API key:        $BGS_TRANSLATOR_KEY_OPENROUTER     │
│                  [LOADED]   [Show value]            │
│                                                      │
│  [ Edit ]  [ Probe ]  [ Set Active ]  [ Delete ]   │
└─────────────────────────────────────────────────────┘
```

### 4.2 Edit dialog

```
┌─ Edit Profile: openrouter-claude ──────────────────────┐
│  Name:             [ openrouter-claude          ]      │
│  SDK kind:         [ openai-compat         ▾ ]         │
│  Base URL:         [ https://openrouter.ai/api/v1 ]    │
│  Model:            [ anthropic/claude-sonnet-4.5 ]     │
│                                                         │
│  API Key:          [ sk-or-***********...        ]     │
│                    [Show] (toggles mask)               │
│                    Stored in profiles/.env             │
│                    Env var name:                       │
│                    BGS_TRANSLATOR_KEY_OPENROUTER       │
│                                                         │
│  Max concurrency:  [ 3 ]                               │
│  Rate limit RPM:   [ 100 ]                             │
│  Rate limit TPM:   [ 0 (no limit) ]                    │
│  Cost cap USD:     [ 10.00 ]                           │
│                                                         │
│  [openai-compat options]                               │
│  JSON mode:        [ json_schema       ▾ ]             │
│  Require params:   [x]                                 │
│  Extra headers:    [ HTTP-Referer=... ]                │
│                    [+ Add header]                      │
│                                                         │
│           [ Probe ]   [ Save ]   [ Cancel ]            │
└────────────────────────────────────────────────────────┘
```

[Show] button toggles the API key field between masked (`sk-or-***********`) and plaintext. The field accepts paste, supports rect-select copy, etc. — standard text-entry behavior. The plaintext is held in memory only during the dialog lifetime; on Save it's written to `.env` and cleared from the widget.

### 4.3 Adding a new profile

```
[ + Add Profile ]
   ↓
Dialog opens. Same shape as Edit but with empty fields.
User fills name, SDK kind, base URL, model, key, etc.
Save creates entry in profiles.toml AND adds the key to .env.
```

### 4.4 Agent registering a profile

When the agent runs `xtl profile add new-provider --sdk anthropic --model claude-... --api-key-env BGS_TRANSLATOR_KEY_NEW_PROVIDER ...`:

- Entry is added to `profiles.toml`
- The agent reports back to the user via chat:
  > "I've registered profile `new-provider` for Anthropic. To activate it, please open the Tk panel (Profiles tab → new-provider → [Edit] → [Show]), or add this line to `~/.bgs-modding-superpowers/translator/profiles/.env`:
  > 
  > `BGS_TRANSLATOR_KEY_NEW_PROVIDER=<your key>`
  > 
  > Then run `xtl profile probe new-provider` to verify."

---

## 5. Profile switching

### 5.1 Active profile

There is exactly one **active** profile at any time, set via:
- `xtl profile activate <name>`
- Tk Profiles tab → [Set Active] button on a card
- Per-project override: `project.toml` → `active_profile`

### 5.2 Switching mid-session

Switching the active profile **takes effect on the next batch dispatched**. In-flight batches use the profile they were dispatched with (snapshot at dispatch time).

```python
@dataclass(frozen=True)
class BatchDispatchSnapshot:
    """Captured at dispatch time; immutable."""
    profile_name: str
    sdk_kind: str
    base_url: str
    model: str
    api_key: str        # Held in memory for request lifetime, then released
    max_concurrency: int
    rate_limit: RateLimit
```

GUI Batches tab shows the snapshot's `profile_name` per row, regardless of current active.

### 5.3 Per-project default

A project can pin to a non-default profile by setting `[settings] active_profile = "..."` in `project.toml`. CLI commands run inside that project use it unless `--profile <other>` overrides.

---

## 6. Probe behavior

`xtl profile probe <name>` sends one tiny test request to determine capabilities.

### 6.1 What the probe does

1. Resolve API key from `.env`
2. Construct a minimal request (1 short item, mock schema)
3. Dispatch via the appropriate SDK
4. Observe headers and response shape
5. Return capability report

### 6.2 Capability report

```json
{
  "ok": true,
  "data": {
    "profile": "openai-prod",
    "reachable": true,
    "ping_ms": 124,
    "model_responsive": true,
    "structured_output_supported": true,
    "structured_output_mode": "json_schema_strict",
    "rate_limit_headers_observed": true,
    "rate_limit_suggested_rpm": 500,
    "rate_limit_suggested_tpm": 200000,
    "cost_in_response": false,
    "prompt_caching_supported": true,
    "cancellation_clean": true,
    "cost_for_probe_usd": 0.0001,
    "raw_headers": { ... },
    "warnings": []
  }
}
```

Probe results are cached for 24 hours per profile (in `.probe-cache.json`). Subsequent dispatches log the probed capabilities for audit.

### 6.3 Per-`sdk_kind` probe variation

| `sdk_kind` | Probe request | Probe checks |
|---|---|---|
| `openai` | Tiny `responses.create` with json_schema strict | `text.format` works, usage returned, headers carry rate limit |
| `anthropic` | Tiny `messages.create` with tool use strict | tool use returns, prompt caching headers in usage, rate limit headers |
| `gemini` | Tiny `generate_content` with response_schema | usage_metadata, schema honored |
| `openai-compat` | Tiny `chat.completions.create` with `response_format` per profile setting | response_format honored, usage in body, optional cost field |

---

## 7. Cost reporting per provider

| Provider | Cost in response | Strategy |
|---|---|---|
| OpenAI (Responses) | No dollar field | Compute from `usage` × local pricing table |
| Anthropic (Messages) | No dollar field | Compute, but accounts for cache_read tokens (cheaper) |
| Gemini (generate_content) | No dollar field | Compute from `usage_metadata` |
| DeepSeek (chat completions) | No dollar field | Compute |
| OpenRouter (chat completions) | **Yes** — `usage.cost` and `usage.cost_details` | Use directly; `cost_exact = true` |
| Other openai-compat | Provider-dependent | Compute fallback |

Local pricing table: `~/.bgs-modding-superpowers/translator/config/pricing.toml`, user-editable. Shipped defaults updated per release. See `10-cost-rate-cancel.md` §3.

---

## 8. Why no LiteLLM

We considered LiteLLM as a unified abstraction across providers. Rejected, with reasons:

- LiteLLM hides Anthropic prompt caching configuration
- LiteLLM hides OpenRouter's exact cost field in response
- LiteLLM normalizes rate limit headers away, losing provider-specific tuning data
- LiteLLM's structured-output handling validates client-side after generation, while native SDKs use provider-side grammar/schema constraints
- LiteLLM adds another failure surface between our code and the provider's actual behavior

For a tool whose value depends on careful cost accounting, prompt-caching savings, and structured-output reliability, the abstraction tax is too high.

LiteLLM may show up later as `sdk_kind = "litellm"` for advanced users who explicitly opt in, but it's not in the core path.
