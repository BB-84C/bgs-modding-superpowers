# Chunk L.2 — Gap Audit (Honest Post-iter4 Reality Check)

Date: 2026-06-07
Trigger: User acceptance test of iter4 GUI revealed iter4's "SHIPPABLE 94/100" was wrong. Many surfaces I labeled as polished MVP are actually unimplemented placeholders.

This doc is the substrate for Chunk L.2 — the FULL implementation of PRD `07-tk-control-panel.md` that iter1-iter4 explicitly deferred. Source: explorer recon + observer screenshot read + librarian fetch + inline CLI sampling.

---

## 1. Mod context was wrong

**`adwryos.esm` is "RYOS — Roll Your Own Start" by Wynterhawk** (Bethesda Creation `c27a121a-c565-4ae0-9394-c58952c98f86`). Alternate-start mod for Starfield, not "spaceship parts pack" as I previously guessed.

CLI-sampled signature inventory (22 distinct sig:field groups, top-N by source content):

| sig:field | count | content type | sample edids / source |
|---|---|---|---|
| MESG:ITXT | 236 | menu choice items | adwCompanionSelectionMessage → "None", "Ezekiel", "Gideon Aker" |
| MESG:DESC | 79 | menu help-text | "If you wish to hire a crew member, pick one..." / "Destination: <Alias=LocationTextAlias> As you stand on the tarmac..." / "If you are doing an NG+ start, you may choose..." |
| MESG:FULL | 79 | menu titles | "Select Crew Member" / "Detour" / "Select a Starborn Power [Pg 04]" |
| MESG:NNAM | 79 | menu nav names | same as FULL |
| QUST:NNAM | 52 | quest stage names | MQ101 → "Follow Supervisor Lin" / "Get the Cutter" / "Collect Mineral Deposits" |
| INFO:NAM1 | 35 | dialog responses | "You've heard of Constellation?" / "We can usually tell where you've been by what you..." / "Take a look. I'm sure I have something you'll need." |
| QUST:CNAM | 21 | quest log entries | MQ101 → "Whatever I found in the mine knocked me out cold." / "Pirates are attacking us! We need to fend them off." |
| PKIN:FULL | 13 | placeable kit names | "AK Wood Awning" / "Canvas Awning" / "Akila Round Cornered Planter" |
| QUST:FULL | 12 | quest titles | "One Small Step" / "New Game Plus Standard Handling" / "The Audition" |
| NPC_:FULL | 10 | NPC display names | "Weapons Specialist Ames" / "Quartermaster Karsovitch" / "Private Mendez" |
| NPC_:SHRT | 10 | NPC short names | "Jesse" / "Nadia" / "Mendez" |
| CELL:FULL | 9 | cell names | "Impound Warehouse 02" / "Argos Extractors Mining Outpost" / "Mess Hall" |
| ACTI:FULL | 6 | activator names | "The Lodge" / "adw Ship Created Trigger" / "Ryos Ship Vendor List" |
| CONT:FULL | 6 | container names | "Ryos Geare Container" / "Ryos Base Container" / "Ryos Vendor Medical Items" |
| WRLD:FULL | 5 | worldspace names | "New Atlantis" / "Argos Extractors Mining Outpost" / "Akila City" |
| BOOK:FULL | 4 | book/holotape titles | "RYOS Mod Information" / "Ship Transaction Slate" / "RYOS Fail-Safe" |
| LCTN:FULL | 2 | location names | "Impound Yard" / "Akila" |
| FACT:FULL | 1 | "Ryos Vendor Faction" |
| TERM:FULL | 1 | "Computer" |
| TMLM:FULL | 1 | "Terminal" |
| BOOK:ENAM | 2 | book inscription | "Funds Transfer" / "SSNN Headlines" |
| BOOK:FNAM | 2 | book metadata | "Acct: 78b2931ae4005" / "Brought to you by TerraBrew" |

**Real translation register**: dominated by (1) UI menu strings (MESG family ~473 entries — choice menus for ship/crew/power/backstory pickers) and (2) short narrative backstory blurbs in MESG:DESC ("As you stand on the tarmac..."). Minor amounts of dialog (INFO:NAM1) and quest log entries. Add to that: a Freestar Militia Impound Facility POI on Montara Luna (NPCs, vendors, mess hall, ship vendor counter).

Updated slot values for sample system prompt:

```
mod_context_name: RYOS — Roll Your Own Start
mod_context_theme: Alternate-start mod for Starfield. Adds player-facing choice menus to pick a starting scenario (custom / pedestrian / ship-owner / NG+ Starborn), starting credits, ship, crew, level, destination, whether main quest "One Small Step" begins. Adds new POI on Montara Luna (Freestar Militia Impound Facility) with vendors, workbenches, mission terminals, medical bay. Per-start backstory blurbs in MESG:DESC explain the player's predicament.
style_directives: Dominated by UI choice menus + short narrative backstory blurbs. Tone: straight Starfield lore-friendly, matter-of-fact NASA-punk register, NOT comedy/parody. Menu strings should be terse/imperative paralleling vanilla Starfield UI ("选择起始信用点数"). Tooltip strings: explanatory, neutral, second person. Backstory blurbs: second-person narrative paragraphs matching vanilla character-creation background register. Preserve <Global.*> placeholders verbatim. Don't expand acronyms (UC, FC, NG+, SAM) into Chinese. Proper nouns: 蒙塔拉卫星 Montara Luna / 自由星系民兵 Freestar Militia / 维克特拉矿场 Vectera Mine / "迈出一小步" One Small Step / 新亚特兰蒂斯 / 阿基拉城 / 塞多尼亚 / 霓虹城 / 星生 Starborn / 大一统 Unity — match vanilla Starfield localization, don't retranslate.
```

---

## 2. GUI tab implementation status (current state)

| Tab | File | LOC | Status | Critical gaps vs PRD §3 |
|---|---|---|---|---|
| §3.1 Project | project_tab.py | 354 | ⚠ Partial | Click-row jumps to Entries not wired; Always-preview toggle doesn't write settings; Rescan/Project-settings buttons are stubs |
| §3.2 Entries | entries_tab.py | 24 | ✗ Placeholder | ENTIRE TAB missing |
| §3.3 Batches | batches_tab.py | 24 | ✗ Placeholder | ENTIRE TAB missing — this is the PRIMARY monitoring surface per PRD |
| §3.4 Prompt | prompt_tab.py | 24 | ✗ Placeholder | ENTIRE TAB missing — this is where Prompt-preview lives per PRD §4.4 |
| §3.5 Profiles | profiles_tab.py | 216 | ⚠ Read-only shell | List+detail read-only OK; Add/Edit/Delete/Save/Probe all stubs; no API key write path; no card layout per PRD |
| §3.6 Glossary | glossary_tab.py | 24 | ✗ Placeholder | ENTIRE TAB missing |
| §3.7 Logs | logs_tab.py | 206 | ⚠ Partial | Tail+filter OK; missing Pause/Resume toggle, Open-folder button, multi-day log nav |

---

## 3. App-level cross-cutting gaps

| PRD ref | Feature | Status |
|---|---|---|
| §1.5 keyboard shortcuts (Ctrl+1..7, Ctrl+B, etc) | ✗ ZERO bound |
| §1.3 i18n live switch | ⚠ Cosmetic only — only notebook tab captions refresh; ~25 hardcoded English strings bypass `_()` |
| §4.1 asyncio↔Tk update_queue bridge | ✗ NOT IMPLEMENTED — no transport for batch progress events into GUI |
| §4.2 two-stage close dialog with detached runner | ✗ Single-stage Cancel/Save only; no Close-window-only branch; no unsaved-translation count; no billing warning |
| §4.3 per-batch cancellation confirmation | ✗ NOT IMPLEMENTED (depends on Batches tab) |
| §4.4 prompt-preview IPC (named pipe / unix socket) | ✗ NOT IMPLEMENTED — `core/ipc.py` + `core/runtime_pid.py` are TODO stubs |
| §5 settings persistence on resize/close | ⚠ Loaded at startup, never persisted on user changes |

---

## 4. Window state — root cause of resize crash

`wm_overrideredirect(True)` (iter3) stripped Win32 chrome. Native edge/corner resize handles, Win32 SC_MAXIMIZE state, Aero Snap, native taskbar-preview-maximize all gone. Custom replacements:

| Capability | Custom replacement status |
|---|---|
| Drag-to-move titlebar | ✓ Implemented (amber_titlebar.py:223-246) |
| 8-zone edge/corner resize hit-test | ✗ NOT IMPLEMENTED — no widget, no `<Motion>` cursor flip, no `<B1-Motion>` resize handler. Window is effectively size-locked. |
| Win32 SC_MAXIMIZE | ✗ Custom geometry hack (amber_titlebar.py:200-215) sets work-area geometry. Win32 never knows window is maximized → taskbar preview wrong, Aero Snap doesn't engage. |
| Restore from maximize | ⚠ `_saved_geometry` stash, no `<Configure>` reconciliation; stale if monitor reconnects or DPI changes |
| Maximize-then-drag | ✗ BUG (the "crash" user reported): `_on_drag_start` restores geometry then anchors against post-restore coords → window snaps back to pre-maximize size but cursor anchor calculation wrong → violent jump. Not an exception, but feels like a crash. |
| Aero Snap (Win+Arrow) | ✗ NOT IMPLEMENTED |
| Native window-state persistence across sessions | ✗ NOT IMPLEMENTED |

**Fix approach (iter5)**: keep amber custom titlebar (preserves the user-approved aesthetic) but add 8-zone hit-test on the outer 1px frame. Cursor flips to sizing cursors near edges/corners. Drag resizes via `geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")`. Add Win32 `WM_SYSCOMMAND` dispatch for SC_MAXIMIZE/SC_RESTORE to properly engage taskbar preview + Aero Snap.

---

## 5. i18n hardcoded-string inventory

en.po has 38 msgids, zh_CN.po 38 msgstrs (100% catalog coverage). But ~25 UI strings in `.py` files bypass `_()`:

- `project_tab.py:113-122` metadata captions ("Project", "Source", "Target", "Game", "Created", "Plugin", "Plugin SHA", "Active profile", "Cost cap") — f-string wrapped, bypasses lookup
- `project_tab.py:170-171` EmptyStatePanel constructor literals
- `project_tab.py:309` error template English-only
- `profiles_tab.py:81-90` ProviderProfile field captions — same f-string-bypass
- `profiles_tab.py:174` "(active)" string suffix
- `logs_tab.py:58, 66` combobox values arrays — never translated
- `logs_tab.py:105-106` EmptyStatePanel literals
- `widgets/empty_state.py:31-32` default caption constants
- `widgets/secret_input.py:39, 48` Show/Hide button text
- `gui/app.py:133` + `amber_titlebar.py:67` window title (proper noun — acceptable exception)

---

## 6. Chunk L.2 fix plan (4 parallel fixer dispatches)

| Fixer | Scope | Files touched | Dependencies |
|---|---|---|---|
| **A — Window infra** | 8-zone resize hit-test + Win32 SC_MAXIMIZE + fix maximize-then-drag + close_handler two-stage + asyncio↔Tk update_queue bridge + window-state persistence on `<Configure>` + Ctrl+1..7 / Ctrl+B / Esc shortcuts + settings-persist-on-change | gui/app.py, gui/widgets/amber_titlebar.py, gui/close_handler.py, NEW gui/widgets/resize_handles.py, NEW core/event_queue.py | BLOCKER for testing other tabs — fix this first |
| **B — Display tabs** | Entries tab full impl (filter row + virtual-scrolled table + row-detail pane + context menu); Batches tab full impl (run-selector + per-batch rows + sparklines + cancel actions) | gui/tabs/entries_tab.py, gui/tabs/batches_tab.py, helper widgets | depends on A's event_queue for Batches live updates |
| **C — Prompt + IPC** | Prompt tab full impl (batch selector + editable Text + approve/discard buttons); IPC server in GUI process; client-side IPC sender in CLI batch run path; runtime_pid for GUI-alive detection | gui/tabs/prompt_tab.py, NEW core/ipc.py (real impl), NEW core/runtime_pid.py (real impl), wire into cli/batch.py | depends on A's event_queue |
| **D — Profiles + Glossary + i18n** | Profiles tab Add/Edit/Delete/Save/Probe dialogs (full ProviderProfile form including SecretInput write path); Glossary tab 4 sub-tabs (vanilla / mod / player / DNT) with table + filter + add/edit dialogs; Wrap all ~25 hardcoded English strings with `_()` and add to .po; logs_tab Open-folder + Pause toggle + multi-day nav | gui/tabs/profiles_tab.py, gui/tabs/glossary_tab.py, gui/tabs/logs_tab.py, gui/i18n/{en,zh_CN}.po, ~10 hardcoded-string sites across tabs/widgets | independent of A/B/C; can run in parallel |

After all 4 return: re-run live capture + strict observer for verification.

---

## 7. Acknowledgment

iter1-iter4 polish work was real, but the underlying scope assessment was wrong. I labeled the placeholder-stub state as "MVP" and let SHIPPABLE verdict pass at 94/100 without flagging that 4 of 7 tabs were 24-line placeholders. User's complaint is justified — the polish was on a foundation that wasn't actually built.

Going forward: Chunk L.2 work is committed as discrete chunks, each verified, each landing on `feat/translator-tool` in dependency order. Estimated 4-6 fixer dispatches + 1-2 observer passes.
