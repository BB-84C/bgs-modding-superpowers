# bgs-translator Web Rewrite — Tk-to-Web Mapping

Date: 2026-06-08

Purpose: Phase 9 acceptance requires every Tk control-panel flow to have an explicit web counterpart or an explicit deferral. This document maps the current Tk tree under `tools/bgs-translator/bgs_translator/gui/` to the browser GUI under `tools/bgs-translator/bgs_translator/web/`.

## Shell, Navigation, And Runtime

| Tk flow | Tk source | Web counterpart | Evidence | Status |
|---|---|---|---|---|
| App shell with project tree, top status bar, tab notebook | `gui/app.py`, `gui/widgets/status_bar.py` | Browser shell with left tree, top status strip, seven route tabs | `_shell_html`, `_sidebar_html`, `_tabs_html`; `tests/web_e2e/test_parity_contracts.py::test_all_top_level_tabs_have_stable_markers` | Implemented |
| Theme selection amber/green/mono | `gui/themes/*`, `StatusBar` theme picker | Header theme selector, class-scoped CSS variables | `web/themes/*.css`; `test_theme_language_api_and_shell_labels`; Browser QA in handoff | Implemented |
| Language selection zh-cn/en | `gui/i18n/*.po`, `StatusBar` language picker | Header language selector with PO-backed loader | `web/i18n/loader.py`; `test_web_i18n_loader_reads_inherited_po_catalog`; Browser QA in handoff | Implemented |
| Refresh shortcut | `gui/app.py` `Ctrl+R` | `Ctrl+R` refreshes Batches/Logs or reloads current page | `_settings_script`; `test_keyboard_shortcut_script_maps_ctrl_digits_and_escape` | Implemented |
| Tab navigation | Tk `Notebook` + nav tree selection | Browser routes `/project`, `/entries`, `/batches`, `/prompt`, `/profiles`, `/glossary`, `/logs`; `Ctrl+1..7` | `_settings_script`; Browser QA `Ctrl+B`, `Ctrl+7` | Implemented |
| GUI PID/lifecycle marker | `core/runtime_pid.py`, Tk app startup | Web launch writes `gui.pid`, `gui.port`, `gui.secret`; CLI discovers web preview | `launch_web`, `core/web_ipc_client.py`, `tests/web_e2e/test_full_acceptance.py` | Implemented |

## Project

| Tk flow | Tk source | Web counterpart | Evidence | Status |
|---|---|---|---|---|
| Select/load project from nav tree | `gui/app.py`, `gui/tabs/project_tab.py` | Default project auto-loads; Project page shows summary and sidebar project entry | `_project_html`, `_project_summary` | Implemented |
| Display project game/unit/cost summary | `ProjectTab.load_project` | Project metrics grid and details table | `_project_html`; Browser desktop QA | Implemented |
| Explain workflow to ordinary players | `ProjectTab` help copy | Chinese-first workflow; SST explained as xTranslator import file, not MOD body | `_project_html`; `test_project_html_explains_sst_and_reload_safely` | Implemented |
| Reload project state | Project/close helpers | `重新读取项目文件` button marker exists; no destructive mutation | `_project_html`, `btn-reload-project` | UI present; action still lightweight/no-op |
| Export on close / unsaved manual edit close prompt | `gui/close_handler.py`, `ProjectTab._on_export`, `ProjectTab._on_open_exports` | Project page has `导出 xTranslator 文件`, `打开导出目录`, close-risk summary, and browser `beforeunload` warning for running batches or manual edits newer than latest export; internal tab navigation bypasses the warning | `/api/projects/{project}/export`, `/api/projects/{project}/open-exports`, `/api/projects/{project}/close-summary`; Browser desktop QA | Implemented with browser constraints |

## Prompt Preview

| Tk flow | Tk source | Web counterpart | Evidence | Status |
|---|---|---|---|---|
| Browse planned batch prompts | `gui/tabs/prompt_tab.py::_load_plans` | Prompt page reads recent `plan.json`, newest first, player-readable batch labels | `_planned_batches`; `test_planned_batch_labels_are_player_readable` | Implemented |
| Show system prompt editor | `PromptTab._build_editor_with_linenos` | Prompt textarea with current system prompt | `_prompt_html`, `field-prompt-body` | Implemented |
| Show glossary subset and DNT panels | `PromptTab._build_side_panel` | Side panels for matched glossary and do-not-translate terms | `_prompt_html`, `_prompt_script`; `test_prompt_html_exposes_preview_markers` | Implemented |
| Preview-required toggle | `PromptTab._build_batch_selector` | Prompt checkbox persists `behavior.prompt_preview_required` | `_prompt_html`, `/api/settings/behavior/prompt_preview_required` | Implemented |
| CLI preview request blocks until user responds | `core/ipc.py`, `gui/app.py::_handle_preview_request` | HTTP `/api/preview/request` + WS broadcast + `/api/preview/respond/{run_id}/{batch_id}` | `core/web_ipc_client.py`; `tests/web_e2e/test_full_acceptance.py`; live runs `rn_ea036975f0de`, `rn_751060ff33f2` | Implemented |
| Approve current batch | `PromptTab._respond_to_preview("approved")` | `确认并翻译` posts `op=approved` | `_prompt_script`; Browser/live acceptance | Implemented |
| Approve all remaining | `PromptTab._respond_to_preview("approve_all")` | `后续全部按这样继续` sets run approve-all server state | `/api/preview/request`, `/api/preview/respond`; live run `rn_ea036975f0de` | Implemented |
| Discard batch | `PromptTab._respond_to_preview("discarded")` | `跳过本批` returns discarded response | `_prompt_script`, `_discarded_response` path remains in CLI | Implemented |
| Auto-focus Prompt tab on preview | `gui/app.py::_focus_prompt_preview` | Browser tab receives WS/polling and renders pending preview in Prompt page | `_prompt_script` pending reconciliation; full acceptance test | Implemented |

## Batches

| Tk flow | Tk source | Web counterpart | Evidence | Status |
|---|---|---|---|---|
| Show recent runs | `BatchesTab._recent_runs` | Run selector backed by sqlite `runs` | `/api/projects/{project}/runs`, `_batches_html`, `_batches_script` | Implemented |
| Show batch rows/progress/cost/status | `BatchesTab._render_tree` | Batches table with progress bars and cost cells | `/api/projects/{project}/runs/{run_id}/batches`; Browser live acceptance | Implemented |
| Live updates from runner events | `EventQueueBridge` in Tk | Durable sqlite `events` plus best-effort HTTP push/WebSocket | `core/event_publisher.py`, `runner.py`; live `rn_ea036975f0de` | Implemented |
| Reconcile after late join | `BatchesTab.load_project/load_run` from sqlite | API rebuilds rows from sqlite batches or events | `_batch_rows`, `_batch_rows_from_events`; `test_run_batches_and_events_api_read_project_sqlite` | Implemented |
| Retry-aware final status | `BatchesTab` row state | Final batch status follows final runner outcome; retry_count persists | `test_retry_success_marks_batch_complete`; post-fix live `rn_751060ff33f2` | Implemented |
| Cancel run | `BatchesTab._cancel_run` calls `xtl batch cancel` | Batches page has `请求停止`; it writes the same `cancel.requested` marker and warns that already-sent AI calls may still cost money | `/api/projects/{project}/runs/{run_id}/cancel`; `test_cancel_run_api_writes_cli_compatible_marker`; Browser desktop QA | Implemented |

## Entries

| Tk flow | Tk source | Web counterpart | Evidence | Status |
|---|---|---|---|---|
| Filter entries by signature/field/status/search | `gui/tabs/entries_tab.py` | Entries toolbar + `/api/projects/{project}/entries` filters | `_entries_html`, `_entries_script`; `test_entries_api_filters_and_saves_manual_edit` | Implemented |
| Select row and show source/dest split | `EntriesTab` detail pane | Source textarea and destination textarea in detail panel | `_entries_html`, `_entries_script` | Implemented |
| Save manual edit | `EntriesTab` save | POST entry dest/status; writes memory + manual edit audit | `/api/projects/{project}/entries/{row_id}`; `test_entries_api_filters_and_saves_manual_edit` | Implemented |
| Restore/lock/clear controls | Tk buttons | Browser buttons `恢复原文`, `锁定原文`, `清空` | `_entries_html`, `_entries_script` | Implemented |

## Profiles

| Tk flow | Tk source | Web counterpart | Evidence | Status |
|---|---|---|---|---|
| List provider profiles without secrets | `ProfilesTab` | Profiles table with active/key status, no key echo | `/api/profiles`; `test_profiles_api_saves_activates_and_masks_key` | Implemented |
| Add/edit profile | `ProfilesTab` dialogs | Visible form with ordinary-player setup steps and visible advanced settings | `_profiles_html`, `_profiles_script`; `test_profiles_advanced_settings_are_visible_not_collapsed` | Implemented |
| Strip endpoint suffix from base URL | `ProfilesTab` save validation | API strips `/chat/completions`, `/responses`, etc. | `_profile_from_payload`; `test_profiles_api_saves_activates_and_masks_key` | Implemented |
| Save API key locally without echoing value | `SecretInput`, Set-API-key dialog | API key value input plus read-only env/local save label | `/api/profiles/{name}/key`; `test_profiles_api_saves_activates_and_masks_key` | Implemented |
| Probe provider and hard-fail missing key | `ProfilesTab` probe | `/api/profiles/{name}/probe`; missing key returns explicit error | `test_profiles_probe_missing_key_hard_fails` | Implemented |
| Activate/delete profile | `ProfilesTab` actions | Activate/delete APIs and buttons | `/api/profiles/{name}/activate`, `DELETE /api/profiles/{name}` | Implemented |

## Glossary

| Tk flow | Tk source | Web counterpart | Evidence | Status |
|---|---|---|---|---|
| Switch scopes vanilla/mod/player/DNT | `GlossaryTab` segmented scope | Browser scope tabs with Chinese labels | `_glossary_html`, `_glossary_script`; Browser QA | Implemented |
| Vanilla/mod read-only guidance | `GlossaryTab` add button state | Add disabled with guidance that the tool automatically maintains those read-only layers | `/api/glossary`; `test_glossary_api_scope_gating_and_player_entry_reaches_next_plan` | Implemented |
| Player/DNT add/edit/delete | `GlossaryTab` add dialog | REST add/edit/delete for player and do-not-translate entries | `/api/glossary`, `/api/glossary/{record_id}`; Browser QA | Implemented |
| Field helpers for ordinary players | `GlossaryTab` dialog helper text | Helper panel explains source/target/aliases/category/notes | `_glossary_html`; `test_glossary_html_exposes_phase7_markers` | Implemented |
| Added player entry reaches next plan | Tk/CLI glossary composer | API-added `Starborn -> 星生子` appears in next `plan.json` prompt subset | `test_glossary_api_scope_gating_and_player_entry_reaches_next_plan` | Implemented |

## Logs

| Tk flow | Tk source | Web counterpart | Evidence | Status |
|---|---|---|---|---|
| Show recent event stream | `LogsTab` | Logs page shows player-facing event labels | `_logs_html`; `test_logs_html_uses_player_facing_event_labels` | Implemented |
| Show status and validator failures | `LogsTab` / batch logs | Logs file viewer reads `status.toml` and `validator-failures.jsonl` | `/api/projects/{project}/runs/{run_id}/logs`; `test_run_logs_api_reads_status_failures_and_safe_files` | Implemented |
| Inspect run files | Tk logs tab | File buttons for status/results/system prompt/plan with player-facing labels | `_logs_script`; `test_logs_script_uses_player_facing_file_labels` | Implemented |
| Path traversal protection | N/A in Tk | Safe root-level file reads only | `_safe_log_file_name`; `test_run_logs_api_reads_status_failures_and_safe_files` | Implemented |

## Tk-Only Infrastructure Marked For Phase 12 Removal

| Tk-only item | Current role | Web replacement | Phase 12 action |
|---|---|---|---|
| `core/ipc.py` | Named-pipe/Unix-socket preview IPC | HTTP preview API and `core/web_ipc_client.py` | Delete |
| `EventQueueBridge` | Process-local GUI events | sqlite `events` + `EventPublisher` | Remove bridge class after Tk deletion; keep `GuiEvent` types if useful |
| Tk widget library | Amber checkbox/scrollbar/titlebar/resize widgets | CSS/HTML shell and browser controls | Delete with `gui/` |
| `tests/gui/` | Tk widget regressions | `tests/web_e2e/` | Delete or replace with web tests |
| Tk default backend | `xtl gui` used to default to Tk | Phase 11 flips default to web after user signoff; `--backend tk` remains available | Implemented |

## Known Gaps Before Cut-Over

- Phase 11 default flip received explicit user signoff on 2026-06-09.
- Tk deletion is not part of the current cut-over scope; it remains a future separate workstream.
- Phase 12 Tk deletion is not started; this mapping is the audit input for that deletion.
