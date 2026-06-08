# bgs-translator Web Rewrite — Acceptance Criteria + Test Strategy

> See `00-spec.md` for intent, `01-architecture.md` for tech design, `02-phases.md` for execution plan.
> This doc owns: per-phase semantic acceptance, Playwright marker conventions, risk register.
> Per memory rule 10-* (semantic proof and acceptance design): acceptance is design-time work, not closeout. Every phase must prove its semantics in real production scenarios.

---

## 1. Semantic acceptance principles

This rewrite must produce **structural fixes**, not surface fixes. A "test passes" outcome is necessary but not sufficient. Each phase must demonstrate:

1. **Real production scenario executed** (`把真实生产 scenario 都走一遍`).
2. **Readback artifact preserved** under `.opencode/artifacts/web-rewrite-acceptance/phase-N/`.
3. **Reviewer audit possible** — anyone (oracle, user, or future agent) can inspect the preserved evidence and judge correctness without rerunning the phase.
4. **Cross-process verification** where the change touches process boundaries (Phases 1, 3, 4, 10).

Acceptance failure on any phase blocks the next phase. No "we'll fix it later" — the bug surfaced in Phase 1 has gotten cheaper, not more expensive, to fix now.

## 2. Per-phase acceptance gates

### Phase 0 acceptance

| Item | Acceptance command | Pass criterion | Artifact |
|---|---|---|---|
| Skeleton compiles | `python -c "import bgs_translator.web"` | Exits 0 | — |
| Smoke test passes | `pytest tests/web_e2e/test_smoke.py -v` | 1 passed | `.opencode/artifacts/web-rewrite-acceptance/phase-0/test-output.log` |
| Backend untouched | `pytest tests/pipeline/ tests/core/ tests/cli/ -q` | No regression vs prior HEAD count | `.opencode/artifacts/.../phase-0/backend-tests.log` |
| Tk path still works | `xtl gui --backend tk` opens Tk window | User confirms in chat | screenshot |

### Phase 1 acceptance

| Item | Acceptance command | Pass criterion | Artifact |
|---|---|---|---|
| Events table created | `sqlite3 memory.sqlite ".schema events"` | Schema matches `01-architecture.md` §3.1 | dump |
| Publisher emits to sqlite | `pytest tests/core/test_event_publisher.py::test_emit_writes_to_sqlite -v` | Passed | log |
| Publisher tolerates absent GUI | `pytest tests/core/test_event_publisher.py::test_emit_swallows_http_push_failure -v` | Passed | log |
| Runner uses publisher | `xtl batch run ryos-zhcn --plan <id> --dry-run; sqlite3 memory.sqlite "SELECT kind, COUNT(*) FROM events GROUP BY kind"` | Returns rows for every emitted event kind | sqlite dump |
| **Bug C structural test** | Synthetic 3-batch run with **no GUI process running**; check `events` table after | All events still persisted to sqlite even without GUI listener | sqlite dump under `phase-1/no-gui-events.sql` |

The last item is the key Phase 1 acceptance — proves the sqlite-as-truth design holds even when the WS push has no listener.

### Phase 2 acceptance

| Item | Acceptance command | Pass criterion | Artifact |
|---|---|---|---|
| Server starts | `xtl gui --backend web --port 7843 --no-open & sleep 2; curl http://127.0.0.1:7843/healthz` | Returns `{"status":"ok"}` | curl output |
| Lifecycle files | `cat ~/.bgs-modding-superpowers/translator/gui.{port,secret,pid}` | Three files, port matches, secret 43+ chars, pid is server's | listing |
| Auth enforcement | `curl http://127.0.0.1:7843/api/preview/request -X POST` | 401 | curl output |
| Auth bypass blocked | `curl -H "Authorization: Bearer wrong" http://127.0.0.1:7843/api/preview/request -X POST` | 403 | curl output |
| All 7 tabs route | `for k in project entries batches prompt profiles glossary logs; do curl -s http://127.0.0.1:7843/$k -o /dev/null -w "$k %{http_code}\n"; done` | All 200 | log |
| Clean shutdown | `kill $SERVER_PID; ls ~/.bgs-modding-superpowers/translator/gui.{port,pid}` | Both files absent | log |

### Phase 3 acceptance — load-bearing

This phase's acceptance is the architectural keystone. If this fails, the rewrite is wrong.

| Item | Acceptance | Pass criterion | Artifact |
|---|---|---|---|
| Synthetic end-to-end | Run synthetic 3-batch plan with browser open + preview-required. Approve each in browser. | All 3 batches complete. Run summary `succeeded=N, cost_usd=0.0`. | screen recording or screenshot per batch + final stdout |
| Approve-all semantics | Same as above; click Approve-all on batch 1. | Batches 2 and 3 dispatch without preview UI re-appearing. | screenshots before/after |
| Discard semantics | Same; Discard batch 1. | Batch 1 returns the synthetic-discarded response (masked sources back as outputs). | sqlite memory.sqlite dest column for that batch |
| Timeout semantics | Patch synthetic client to never respond; CLI POST timeout=5s. | CLI returns `{"op":"timeout"}` after 5s; preview cleared in browser via `preview.timeout` WS event. | log |
| Multi-tab race | Open 2 browser tabs; both see preview-request. Tab A clicks Approve first. | Tab A succeeds. Tab B's Approve POST returns 409. Tab B's preview UI clears via `preview.closed` WS broadcast. | screenshots both tabs |
| No-GUI fallback | Stop GUI server; run synthetic batch. | CLI POST returns `{"op":"no_gui"}` immediately; batches dispatch with original prompt. | log |
| Concurrent runs | Run 2 synthetic batches in parallel (different `run_id`). | Both see preview UI; approving one does not affect the other. | screenshots |

### Phase 4 acceptance

| Item | Acceptance | Pass criterion |
|---|---|---|
| Live event flow | Synthetic 5-batch run with browser open on Batches tab. | 5 rows appear → each progresses → all complete. Total time < 10s for synthetic. |
| Cost chip updates | Same run. | Header cost chip transitions through 5 incremental values. |
| Reconcile on late join | Start synthetic run; close browser tab mid-flight; reopen and navigate to Batches. | Tab shows all events up to current moment (rebuilt from sqlite). |
| Project list loads | Open Project tab. | All discoverable projects listed. |
| Project detail accurate | Click `ryos-zhcn`. | Detail shows correct game (Starfield), unit count, cost-spent matching `project.toml`. |

### Phase 5 acceptance

| Item | Acceptance | Pass criterion |
|---|---|---|
| **Bug D closed** | Open Entries tab, click any unit. | Detail pane shows **both** source AND dest panes (vertical split, each scrollable). |
| Filter by signature | Set sig filter to `MESG`. | Table shows only MESG rows. |
| Search box | Type partial text from a known source. | Table filters live. |
| Edit + save | Edit a unit's dest; click Save. | Re-fetch unit via `/api/entries/{id}` shows updated dest. |
| 500+ row perf | Open project with 500+ units. | Initial render < 1s; scroll smooth. |

### Phase 6 acceptance

| Item | Acceptance | Pass criterion |
|---|---|---|
| **UX 6** | Add profile with `base_url=https://api.openai.com/v1/chat/completions`. | Saved as `https://api.openai.com/v1` with warning shown. |
| **UX 7** | Open Set-API-key for `OpenRouter-DeepSeek`. | Dialog shows env var name `BGS_TRANSLATOR_KEY_DEEPSEEK` as **read-only label**; value field is sole input. |
| **UX 8** | Set api_key_env to a non-existent env var; probe. | Returns hard error `missing_api_key`. |
| Activate profile | Click Activate on a non-active profile. | List re-renders with new active marker. |

### Phase 7 acceptance

| Item | Acceptance | Pass criterion |
|---|---|---|
| **UX 1 vanilla** | Switch Glossary tab to scope=`vanilla`. | Add button disabled; "use AI agent" message shown. |
| **UX 1 mod** | Switch to scope=`mod`. | Add button disabled; "use AI agent" message shown. |
| **UX 1 player** | Switch to scope=`player`. | Add button enabled. |
| **UX 1 dnt** | Switch to scope=`dnt`. | Add button enabled. |
| **UX 2** | Click Add on player scope. | Dialog shows each field with helper text below per spec. |
| Add persists | Add `Starborn → 星生子` with category=`lore_term`. | Replan a batch; verify entry appears in `plan.json` `glossary_subset`. |

### Phase 8 acceptance

| Item | Acceptance | Pass criterion |
|---|---|---|
| Logs tab | Run synthetic batch. | Logs tab shows recent events stream + status.toml + validator-failures.jsonl content. |
| Theme switch | Switch theme dropdown amber → green. | Page reloads with green theme. CSS variables changed. |
| Theme switch | green → mono. | Page reloads with mono theme. |
| Language switch | Switch en → zh-cn. | All tab labels update. |
| Language switch | zh-cn → en. | All tab labels revert. |
| i18n covers all strings | `grep -r 'gettext\|_(' tools/bgs-translator/bgs_translator/web/ | wc -l` | ≥ 50 hits (all user-facing strings wrapped). |

### Phase 9 acceptance

| Item | Acceptance | Pass criterion |
|---|---|---|
| Test suite size | `pytest tests/web_e2e/ --collect-only -q | wc -l` | ≥ 30 tests. |
| Full suite green | `pytest tests/web_e2e/ -v` | All pass. No skips except known platform-specific. |
| Tk-to-web mapping doc | `docs/plans/translator-tool/web-rewrite/09-tk-to-web-mapping.md` | Lists every Tk-version flow + web counterpart. |
| Synthetic acceptance | `pytest tests/web_e2e/test_full_acceptance.py -v` | Full synthetic round-trip in one test. |

### Phase 10 acceptance — semantic e2e

| Item | Acceptance | Pass criterion |
|---|---|---|
| **Bug C closed live** | Real OpenRouter run with web GUI; observe Batches tab during run. | Live updates per batch. Final summary matches reality. |
| Cost accuracy | `events` `cost.update` payloads sum to within ±$0.001 of OpenRouter dashboard. | Within tolerance. |
| Audit artifacts | `ls .../batches/<run-id>/` | `plan.json`, `system-prompt.md`, `responses/*.{raw,normalized}.json`, `results.json`, `status.toml`, `validator-failures.jsonl` all present. |
| Cross-process proof | `sqlite3 memory.sqlite "SELECT COUNT(*) FROM events WHERE run_id = '<id>'"` | Equals N events expected for that run. |
| Reviewer audit | `@oracle` reviews `.opencode/artifacts/web-rewrite-acceptance/phase-10/` | Reviewer confirms semantic correctness. |

### Phase 11 acceptance

| Item | Acceptance | Pass criterion |
|---|---|---|
| Cut-over checklist | All items in `00-spec.md` §6 hold. | Documented in artifact. |
| User signoff | Explicit "ship cut-over" message in chat. | Captured in `docs/dev-log.md`. |
| Default flipped | `xtl gui` opens browser, not Tk window. | Verified manually. |
| Tk still opt-in | `xtl gui --backend tk` opens Tk. | Verified manually. |

### Phase 12 acceptance — completion

| Item | Acceptance | Pass criterion |
|---|---|---|
| Tk tree gone | `git ls-files bgs_translator/gui/ tests/gui/ bgs_translator/core/ipc.py` | Empty output. |
| Imports clean | `grep -r 'import tkinter\|from tkinter' tools/bgs-translator/` | No hits. |
| Test suite green post-removal | `pytest -x -q` | All pass. |
| README updated | `tools/bgs-translator/README.md` | No mentions of Tk. |
| Removal commit | `git log --oneline -1` | Title: `refactor(gui): remove Tk control panel; web is the only surface` |
| Final reviewer pass | `@oracle` reviews final state | Confirms no Tk vestigials. |
| Dev-log entry | `docs/dev-log.md` | Migration completion entry per `writing-modpack-devlog` skill. |

## 3. Playwright marker naming conventions

Every interactive widget gets `.mark("<id>")` in NiceGUI. Playwright addresses via `data-marker` attribute.

### 3.1 Naming rules

```
{role}-{verb-or-name}[-{scope}]
```

| Role prefix | Use |
|---|---|
| `tab-` | Top-level tab nav links |
| `btn-` | Action buttons |
| `field-` | Form inputs / text areas |
| `dialog-` | Dialog root containers |
| `row-` | Table rows (with id suffix) |
| `status-` | Status indicators / chips |
| `nav-` | Side / breadcrumb nav |
| `link-` | Hyperlinks that aren't tabs |
| `panel-` | Layout panels (left/right/top/bottom of a tab) |
| `select-` | Dropdowns |
| `check-` | Checkboxes |
| `radio-` | Radio buttons |

### 3.2 Full marker catalogue (phases 4-8)

Tab nav (set in Phase 2):
- `tab-project`, `tab-entries`, `tab-batches`, `tab-prompt`, `tab-profiles`, `tab-glossary`, `tab-logs`

Shell header (Phase 2 / 8):
- `select-theme`, `select-language`, `status-cost-total`, `status-active-profile`, `status-gui-alive`

Project tab (Phase 4):
- `nav-project-list`, `panel-project-detail`, `btn-reload-project`, `field-search-projects`

Entries tab (Phase 5):
- `panel-entries-filter`, `select-entries-sig`, `select-entries-field`, `select-entries-status`, `field-entries-search`
- `panel-entries-table`, `row-entries-{unit_id}`
- `panel-entry-detail`, `field-entry-source`, `field-entry-dest`
- `btn-entry-save`, `btn-entry-restore`, `btn-entry-lock`, `btn-entry-orphan`

Batches tab (Phase 4):
- `panel-batches-table`, `row-batches-{batch_id}`, `status-batch-progress-{batch_id}`
- `btn-cancel-run-{run_id}`

Prompt tab (Phase 3):
- `select-batch`, `field-prompt-body`, `check-prompt-editable`, `radio-edit-scope-{value}`
- `check-preview-required`
- `panel-glossary-subset`, `panel-dnt-list`
- `btn-approve-batch`, `btn-approve-all`, `btn-discard-batch`

Profiles tab (Phase 6):
- `nav-profiles-list`, `row-profile-{name}`
- `btn-add-profile`, `btn-edit-profile-{name}`, `btn-activate-profile-{name}`
- `btn-probe-profile-{name}`, `btn-set-api-key-{name}`
- `dialog-add-profile`, `dialog-edit-profile`, `dialog-set-api-key`
- `field-profile-name`, `field-profile-base-url`, `field-profile-model`, `field-profile-api-key-env`
- `field-api-key-value` (in Set-API-key dialog)
- `status-base-url-strip-warning`

Glossary tab (Phase 7):
- `tab-glossary-vanilla`, `tab-glossary-mod`, `tab-glossary-player`, `tab-glossary-dnt`
- `panel-glossary-table`, `row-glossary-{record_id}`
- `btn-add-glossary-entry`, `dialog-add-glossary-entry`
- `field-glossary-source`, `field-glossary-target`, `field-glossary-source-lang`, `field-glossary-target-lang`, `field-glossary-category`, `field-glossary-aliases`
- `status-glossary-empty-vanilla`, `status-glossary-empty-mod`, `status-glossary-empty-player`, `status-glossary-empty-dnt`

Logs tab (Phase 8):
- `select-log-run`, `panel-log-stream`, `panel-log-file-viewer`
- `link-log-file-{name}`

### 3.3 Playwright fixture (canonical)

`tests/web_e2e/conftest.py` (full version per `01-architecture.md` §5.1).

Test pattern:

```python
def test_glossary_scope_vanilla_disables_add(page: Page):
    page.get_by_test_id("tab-glossary").click()
    page.get_by_test_id("tab-glossary-vanilla").click()
    add_btn = page.get_by_test_id("btn-add-glossary-entry")
    expect(add_btn).to_be_disabled()
    expect(page.get_by_test_id("status-glossary-empty-vanilla")).to_contain_text("use AI agent")
```

Test ID resolution is configured via `pytest-playwright`'s `testid_attribute=data-marker`.

## 4. Required Playwright test list

Minimum coverage per phase. Add more if natural.

### Phase 0
- `test_smoke.py::test_healthz_returns_200`

### Phase 2
- `test_server_lifecycle.py::test_server_starts_and_responds_to_healthz`
- `test_server_lifecycle.py::test_lifecycle_files_written_then_removed`
- `test_server_lifecycle.py::test_unauthenticated_api_request_returns_401`
- `test_server_lifecycle.py::test_wrong_secret_returns_403`
- `test_server_lifecycle.py::test_shell_renders_all_seven_tab_links`

### Phase 3
- `test_preview_handshake.py::test_request_preview_blocks_then_resolves_on_browser_approve`
- `test_preview_handshake.py::test_approve_all_resolves_subsequent_requests_for_same_run`
- `test_preview_handshake.py::test_discard_returns_discarded_response`
- `test_preview_handshake.py::test_request_returns_no_gui_when_server_down`
- `test_preview_handshake.py::test_concurrent_tabs_first_wins_others_409`
- `test_preview_handshake.py::test_preview_timeout_returns_timeout_op`

### Phase 4
- `test_batches_tab.py::test_synthetic_run_streams_events_to_browser_table`
- `test_batches_tab.py::test_late_joining_tab_reconciles_from_sqlite`
- `test_batches_tab.py::test_cost_update_event_updates_cost_chip`
- `test_batches_tab.py::test_run_cancel_button_writes_cancel_marker`
- `test_project_tab.py::test_project_list_loads`
- `test_project_tab.py::test_project_detail_shows_unit_counts`

### Phase 5
- `test_entries_tab.py::test_detail_pane_shows_both_source_and_dest_panes`  ← **Bug D fix verification**
- `test_entries_tab.py::test_filter_by_signature`
- `test_entries_tab.py::test_search_box_filters`
- `test_entries_tab.py::test_edit_dest_save_persists`
- `test_entries_tab.py::test_table_virtualizes_500_rows_under_1s`

### Phase 6
- `test_profiles_tab.py::test_add_profile_strips_chat_completions_suffix`
- `test_profiles_tab.py::test_set_api_key_dialog_env_name_is_readonly_label`  ← **UX 7 verification**
- `test_profiles_tab.py::test_probe_with_missing_key_hard_fails`  ← **UX 8 verification**
- `test_profiles_tab.py::test_activate_changes_active_marker`

### Phase 7
- `test_glossary_tab.py::test_vanilla_scope_disables_add_button`  ← **UX 1 verification**
- `test_glossary_tab.py::test_mod_scope_disables_add_button`
- `test_glossary_tab.py::test_player_scope_enables_add_button`
- `test_glossary_tab.py::test_dnt_scope_enables_add_button`
- `test_glossary_tab.py::test_add_dialog_shows_all_field_helpers`  ← **UX 2 verification**
- `test_glossary_tab.py::test_added_player_entry_appears_in_next_plan_glossary_subset`

### Phase 8
- `test_logs_tab.py::test_recent_events_stream_renders`
- `test_logs_tab.py::test_log_file_viewer_renders_status_toml`
- `test_theme_switcher.py::test_amber_to_green_changes_body_class`
- `test_theme_switcher.py::test_amber_to_mono_changes_body_class`
- `test_language_switcher.py::test_en_to_zhcn_updates_tab_labels`
- `test_language_switcher.py::test_zhcn_to_en_reverts_tab_labels`

### Phase 9
- `test_full_acceptance.py::test_synthetic_round_trip_end_to_end`
- `test_keyboard_shortcuts.py::test_ctrl_digit_selects_tab`
- `test_keyboard_shortcuts.py::test_escape_closes_topmost_dialog`

## 5. Risk register

Risks the engineer must read before each phase. Update with new risks as they surface.

### High

| Risk | Mitigation | Phase |
|---|---|---|
| NiceGUI long-session leak (#5803) bites with hours of use | `message_history_length=0`, `reload=False`, minimal `ui.timer`, daily restart documented in user guide | 2, 8, 10 |
| Cross-process events don't actually flow (Bug C recurs) | Phase 1 acceptance proves sqlite-as-truth works even with no GUI listener; Phase 10 proves WS push works live | 1, 4, 10 |
| Multiple browser tabs race on the same approve | First-POST-wins on `/respond`; others get 409; WS broadcast greys out other tabs | 3 |
| amber-CRT aesthetic harder in CSS than expected | Reserve 0.5 days in Phase 8 for theme polish; fallback to default Quasar dark if necessary | 8 |
| Playwright fixture slow / flaky across machines | Use `pytest-playwright` defaults; allow 5s startup window for healthz poll | 0, 9 |

### Medium

| Risk | Mitigation | Phase |
|---|---|---|
| `events` table grows unbounded over time | Add `DELETE FROM events WHERE emitted_at < datetime('now', '-30 days')` on GUI startup; configurable | 1 |
| Browser memory exceeds 500 MB after 4h idle | Profile during Phase 10 acceptance; if violated, investigate `ui.refreshable` re-render leaks | 10 |
| User's `gui.port` 7843 collides with another app | Auto-pick 7844..7850 fallback; document in error | 2 |
| Shared-secret file world-readable on Windows | Use ACL restriction (icacls); document fallback for non-NTFS | 2 |
| WS reconnect storm if server restarts | Browser reconnect throttle 1s + backoff | 3, 4 |

### Low

| Risk | Mitigation | Phase |
|---|---|---|
| Browser doesn't auto-open on user's machine | `webbrowser.open` fallback to printing URL | 2 |
| Pydantic version conflict with NiceGUI dep | Pin NiceGUI version range; test in Phase 0 | 0 |
| Playwright Chromium binary install fails in CI | Add `playwright install --with-deps chromium` to test prerequisites doc | 0 |
| `pythonw` no longer needed but lingers in docs | Phase 12 documentation cleanup | 12 |

## 6. Anti-patterns surfaced during acceptance

These are mistakes the engineer might make and shouldn't:

- ❌ Declaring a phase done on test pass without running the manual smoke. Smoke catches semantic gaps tests miss.
- ❌ Preserving acceptance artifacts only on success. **Preserve on failure too** — failed artifacts are the diagnostic for the next round.
- ❌ Skipping the cross-process verification in Phase 1. The whole rewrite is justified by Bug C; if Phase 1 can't prove cross-process flow, stop.
- ❌ Using `winfo_ismapped()` or any Tk-derived assertion idiom in web tests. Use `expect(...).to_be_visible()` instead.
- ❌ Approving in CI without a real browser. Phase 9 + 10 require a real Chromium.
- ❌ Letting the events table grow unbounded "until later." Cleanup goes in Phase 1.
- ❌ Embedding the runner inside uvicorn. The runner is a separate process. If a phase tempts this, escalate to oracle.
- ❌ Adding new functionality during the rewrite. Port-only. New features queue for after Phase 12.

## 7. Reviewer checklist (run before declaring each phase done)

For Phases 0-12:

- [ ] All "Acceptance" items in the per-phase table above are checked.
- [ ] All Playwright tests for the phase pass green.
- [ ] All existing tests still green.
- [ ] ruff + mypy clean.
- [ ] Artifacts preserved under `.opencode/artifacts/web-rewrite-acceptance/phase-N/`.
- [ ] Phase commit lands on `feat/translator-web-rewrite`.
- [ ] Cross-phase invariants (Phase 2 onwards: Tk path still works) hold.
- [ ] **Oracle review** (read-only adjudication) requested for Phases 1, 3, 4, 10, 12.
- [ ] Risk register updated with anything new the phase surfaced.

When all check, mark the phase done in `02-phases.md` (`- [x]` per task) and push.

## 8. Final adjudication

Per memory rule 70-* (permission boundaries): the **user holds final say** on:

- Cut-over (Phase 11) — user signoff required.
- Tk removal (Phase 12) — user signoff required.
- Any deviation from the spec that would skip an acceptance criterion.

Per memory rule 70-* (permission boundaries) and the oracle's architecture review: **never** run a live LLM batch (Phase 10) without explicit user consent before each round. The CLI's cost-cap and rate-limit settings stay enforced.

Acceptance evidence for Phase 10 may **not** be substituted with synthetic-only test results. It must be a real OpenRouter (or other provider) call.

---

This is the contract. Sign off and execute.
