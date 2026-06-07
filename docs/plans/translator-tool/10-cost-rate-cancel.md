# 10 — Cost, Rate Limit, Cancellation

Three closely-related concerns: how we limit spending, how we throttle to provider limits, and what happens when the user pulls the plug.

---

## 1. Cost caps

### 1.1 Two levels

- **Per-profile cap**: `profiles.toml` → `[profiles.<name>] cost_cap_usd`. Tracks spend across all projects using this profile.
- **Per-project cap**: `project.toml` → `[cost] cap_usd`. Tracks spend for this project regardless of profile.

Both checked before each batch dispatch. Whichever triggers first blocks the dispatch.

### 1.2 Cap-reached behavior

When a cap is reached:

1. **In-flight batches are NOT cancelled.** The money has already been committed. Cancelling would not refund.
2. New batch dispatches return error:
   ```json
   {
     "ok": false,
     "error": {
       "code": "cost_cap_exceeded",
       "message": "Profile 'openai-prod' cost cap reached: $5.00 of $5.00 spent.",
       "details": {
         "scope": "profile",
         "name": "openai-prod",
         "cap_usd": 5.00,
         "spent_usd": 5.00,
         "in_flight_cost_estimate_usd": 0.12
       }
     }
   }
   ```
3. GUI shows red banner: `[COST CAP] Profile 'openai-prod' reached $5.00. Lift cap or switch profile.`
4. Agent skill instructs the agent to surface this to the user with the suggested actions (lift cap via Tk Profile edit, or switch to a different profile, or wait for budget reset if applicable).

### 1.3 Adjusting caps mid-session

Via Tk Profiles tab → [Edit] → change cap. New cap takes effect immediately. If in-flight batches put the project above the new cap, no penalty (the cap blocks new, doesn't unwind committed).

Via CLI: `xtl profile edit <name> --cost-cap-usd 20.00` updates the cap.

### 1.4 Tracking accuracy

- **OpenRouter**: `cost_usd` from response is exact; recorded as `cost_exact=true`.
- **All other providers**: cost computed locally as `(tokens_in × price_in + tokens_out × price_out) / 1_000_000` from `pricing.toml`. Recorded as `cost_exact=false`.
- **Provider price changes**: tool's `pricing.toml` may be stale. Users update from project's `defaults/pricing.toml` periodically. Tool warns at startup if pricing.toml is older than 60 days.

### 1.5 Per-profile spend reset

Profile spend accumulates indefinitely. `xtl profile reset-spend <name>` resets the counter to zero (e.g., for monthly billing alignment). GUI Profiles tab has [Reset spend] button.

---

## 2. Rate limit (three-layer)

### 2.1 The three layers

| Layer | Source | Behavior |
|---|---|---|
| 1. Configured ceiling | `profiles.toml` → `rate_limit_rpm`, `rate_limit_tpm` | Hard upper bound. Token bucket initialized at this. |
| 2. Observed ceiling | Response headers (e.g., `anthropic-ratelimit-requests-remaining`, `x-ratelimit-limit-requests`) | If provider reports a lower remaining capacity, the effective ceiling drops to `min(configured, observed)` until the next observation. |
| 3. Reactive 429 backoff | 429 response with optional `Retry-After` header | Pause this profile for the indicated duration. If no header, exponential backoff: 4s, 8s, 16s. |

### 2.2 Token bucket implementation

Per profile, two token buckets:
- Request bucket: `rate_limit_rpm` tokens, refilled at `rate_limit_rpm / 60` per second
- Token bucket: `rate_limit_tpm` tokens, refilled at `rate_limit_tpm / 60` per second

A batch dispatch consumes:
- 1 request token (waits if not available)
- Estimated input + output tokens from token bucket (waits if not available)

If a dispatch can't acquire within 30 seconds, dispatch is deferred (batch goes back to queued state, surfaced in GUI as "throttled").

### 2.3 Observed ceiling header parsing

| Provider | Headers consumed |
|---|---|
| OpenAI | `x-ratelimit-limit-requests`, `x-ratelimit-remaining-requests`, `x-ratelimit-reset-requests`, `x-ratelimit-limit-tokens`, `x-ratelimit-remaining-tokens` |
| Anthropic | `anthropic-ratelimit-requests-limit`, `anthropic-ratelimit-requests-remaining`, `anthropic-ratelimit-requests-reset`, `anthropic-ratelimit-input-tokens-*`, `anthropic-ratelimit-output-tokens-*` |
| OpenRouter | Same as OpenAI (compatibility) |
| DeepSeek | Not documented; ignored if absent |
| Gemini | Per `google-genai` SDK; minimal headers exposed; rely on 429 reactive |

After each response, the rate tracker updates the effective ceiling. GUI Profiles tab card shows:
```
Rate limit: configured 500 RPM, observed 350 remaining (resets in 47s)
```

### 2.4 429 reactive behavior

On 429 from a profile:

1. Parse `Retry-After` header (seconds or HTTP-date format)
2. If absent: backoff starts at 4s, doubles per consecutive 429 (4s, 8s, 16s)
3. Mark profile state as `throttled` for the duration; GUI shows `[!] throttled, retry in Ns`
4. After 3 consecutive 429s within 5 minutes, profile enters `halted` state: no more dispatches until user manually resumes via Tk Profile tab [Resume] button or `xtl profile resume <name>`
5. Halt state returns error to subsequent dispatches:
   ```json
   {
     "ok": false,
     "error": {
       "code": "rate_limit_halted",
       "message": "Profile 'openai-prod' halted after 3 consecutive 429 responses.",
       "details": {"consecutive_429s": 3, "last_429_at": "...", "resume_action": "xtl profile resume openai-prod"}
     }
   }
   ```

### 2.5 Probe-driven defaults

`xtl profile probe <name>` (per `09-providers-and-keys.md` §6) returns suggested rate limit values. User confirms via dialog; tool updates `profiles.toml`.

Default values for new profiles (when probe hasn't run):
- `rate_limit_rpm = 60`
- `rate_limit_tpm = 60000`

Conservative defaults to avoid accidental 429 storms on user's first run.

---

## 3. Cost estimation

### 3.1 Pre-dispatch estimation

When `xtl batch plan` runs:

```python
def estimate_batch_cost(batch: Batch, profile: ProviderProfile) -> CostEstimate:
    # Input estimate: system prompt size + items size
    system_prompt_tokens = tokenize(rendered_system_prompt(batch))
    items_tokens = sum(tokenize(item.source_masked) for item in batch.items) * 1.2  # markup
    input_tokens = system_prompt_tokens + items_tokens
    
    # Output estimate: items size × language expansion factor
    expansion = LANGUAGE_EXPANSION_FACTORS.get(
        (profile.target_lang, batch.register), 1.3
    )
    output_tokens = items_tokens * expansion
    
    # Cost from pricing.toml
    pricing = load_pricing()[profile.sdk_kind][profile.model]
    cost_usd = (input_tokens * pricing.input_per_1m + 
                output_tokens * pricing.output_per_1m) / 1_000_000
    
    # Anthropic prompt caching discount (if applicable)
    if profile.sdk_kind == "anthropic" and profile.prompt_caching:
        # Cached portion: system prompt + glossary subset (relatively stable across batches)
        cached_tokens = system_prompt_tokens * 0.8  # heuristic
        cache_read_cost = cached_tokens * pricing.cache_read_per_1m / 1_000_000
        normal_cost = (input_tokens - cached_tokens) * pricing.input_per_1m / 1_000_000
        cost_usd = cache_read_cost + normal_cost + output_tokens * pricing.output_per_1m / 1_000_000
    
    return CostEstimate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        exact=False,
    )
```

### 3.2 Post-response correction

After response:
- For OpenRouter: use response's `usage.cost` directly. Mark `cost_exact=true`.
- For everything else: recompute with actual `usage.input_tokens` and `usage.output_tokens`. Mark `cost_exact=false`.

The recomputed cost replaces the estimate in `memory.sqlite` and the cumulative profile/project spend.

### 3.3 Language expansion factors

Stored in code (not config); empirical estimates. Updated as data accumulates.

```python
LANGUAGE_EXPANSION_FACTORS = {
    # (target_lang, register) → output/input token ratio
    ("zh-cn", "dialogue"): 1.2,
    ("zh-cn", "ui_label"): 0.8,
    ("zh-cn", "item_name"): 0.7,
    ("zh-cn", "book_prose"): 1.1,
    ("fr", "dialogue"): 1.4,
    ("de", "dialogue"): 1.5,
    # ... defaults to 1.3 if not in table
}
```

### 3.4 Cost display in GUI

Status bar (top): `$0.42 session / $0.42 project`

Batches tab per-row: `~$0.05` for in-flight, `$0.06` (no ~) for OpenRouter completed exact, `~$0.06` for other providers' completed.

Profiles tab per-card: `Cost: $0.42 / $10.00 ●` with progress bar showing spend / cap.

---

## 4. Cancellation semantics

### 4.1 Scope

Cancellation operates at three levels:

| Scope | CLI | GUI |
|---|---|---|
| Single batch | `xtl batch cancel <run_id> --client <n>` | [Cancel] button per row in Batches tab |
| Whole run | `xtl batch cancel <run_id>` | [Cancel run] button at bottom of Batches tab |
| Everything | (no CLI; rare) | "Stop everything" close confirmation |

### 4.2 What cancellation actually does

When triggered:

1. `asyncio.Task.cancel()` is invoked on the dispatch task
2. The task's HTTP request via httpx is closed
3. Local execution unblocks immediately
4. The batch's `BatchDispatchSnapshot` is finalized with `status=cancelled`
5. `cost_estimate_usd` is computed from any partial tokens received (if streaming, which we don't use) or simply marked as "may have been billed"

### 4.3 Billing reality (from Lane 2 research)

We cannot guarantee the provider stops billing:
- Provider may have already begun processing
- Provider may complete generation server-side and bill, even though we discard the response
- Some providers charge for input tokens always, even on cancelled responses
- Streaming-vs-non-streaming has different bill semantics (and we don't stream)

### 4.4 UX language

Both CLI and GUI use consistent language to make this clear to users:

CLI envelope:
```json
{
  "ok": true,
  "data": {
    "run_id": "rn_8af3...",
    "batches_cancelled": 1,
    "cost_committed_estimate_usd": 0.03,
    "cost_status": "estimated",
    "note": "Provider may bill for tokens consumed before client-side abort. Final bill may differ from estimate."
  }
}
```

GUI dialog (per `07-tk-control-panel.md` §4.3):
> "Cancellation stops the local HTTP request immediately. The provider may have already received and begun processing your request. You may still be billed for tokens consumed before the abort takes effect.
> 
> Estimated cost so far: $0.03 [estimated, ±20%]"

### 4.5 Cancellation during retry

If a batch is in retry phase (corrective-feedback retry), cancellation kills the retry attempt. The batch's final status:
- If the previous attempt's items were partially valid: those items are committed; the failing items go to manual-review queue
- If no items were valid yet: entire batch is cancelled, no items committed

### 4.6 Resuming after cancellation

Cancelled batches do NOT auto-resume. User must explicitly:
- Re-run the same plan: `xtl batch run <project> --plan <plan_id>` (skips already-committed items)
- Plan and run anew: `xtl batch plan ... && xtl batch run ...`

This is intentional. Auto-resume risks burning more budget on something the user might have cancelled deliberately.

---

## 5. Concurrency interactions

The three throttles interact:

```
                  Cost cap reached? ────→ block dispatch
                       │ no
                       ▼
                  Rate limit halted? ────→ block dispatch
                       │ no
                       ▼
                  Token bucket available? ────→ wait (up to 30s) or defer
                       │ yes
                       ▼
                  Profile semaphore available? ────→ wait
                       │ yes
                       ▼
                  Dispatch
```

GUI Batches tab shows the actual blocking reason per queued batch:
```
b_5e7...  │  queued (cost cap)
b_5f8...  │  queued (rate limit)
b_6a9...  │  queued (semaphore: 4 in-flight)
```

---

## 6. Audit trail

Every batch records its cost and rate-limit story:

```toml
# batches/<run-id>/status.toml
batch_id = "b_2b4..."
status = "complete"
profile_snapshot = "openrouter-claude"
sdk_via = "chat_completions"
tokens_in = 1240
tokens_out = 1530
cost_usd = 0.06
cost_exact = true              # OpenRouter
rate_limit_observed_rpm = 350  # at dispatch time
rate_limit_remaining_after = 349
retry_count = 0
cancelled = false
```

For cancelled batches:
```toml
batch_id = "b_3c5..."
status = "cancelled"
profile_snapshot = "openrouter-claude"
sdk_via = "chat_completions"
tokens_in = null                # never completed
tokens_out = null
cost_usd_estimate = 0.03
cost_exact = false
cost_status = "estimated_may_have_been_billed"
cancelled_at = 2026-06-06T12:34:56Z
cancelled_by = "user"           # "user" | "cost_cap" | "rate_halt" | "shutdown"
```

These records back the cost-tracker UI and provide forensic data for any "why did this batch cost what it did" question.
