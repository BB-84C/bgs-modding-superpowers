# 07 — Tk Control Panel

## Purpose

The Tk control panel is **configuration and monitoring**, not translation editing. Users configure provider profiles, watch batch progress in real time, preview/edit upcoming system prompts, manage glossary overrides, and audit cost.

**Per-string human translation editing is NOT in this panel.** Users do that in xTranslator or ESP-ESM Translator. The panel exists to give the user a real-time control plane while the agent drives the work, plus the privileged surface for API key entry that the agent cannot perform.

---

## 1. Aesthetic and theming

### 1.1 Look and feel

- **Phosphor terminal aesthetic** with three switchable themes
- Monospace font everywhere (Cascadia Mono / JetBrains Mono / system fallback)
- Unicode box-drawing for borders (`─ │ ┌ ┐ ┘ └ ╔ ╗ ╚ ╝`)
- Text-based status indicators (`[OK]`, `[..]`, `[!]`, `[X]`, `[..▓▒░]`)
- Unicode block characters for sparklines (`▁▂▃▄▅▆▇█`)
- **Zero emoji**

### 1.2 Three themes

| Theme | Background | Foreground | Accent | Style |
|---|---|---|---|---|
| `amber` | `#1a0f00` | `#ffb000` | `#ff8800` | Pip-Boy / vintage CRT |
| `green` | `#001a00` | `#33ff33` | `#00cc44` | Classic phosphor terminal |
| `mono` | `#000000` | `#e0e0e0` | `#a0a0a0` | High-contrast minimal |

Theme is set via `config/settings.toml` → `ui_theme`, or CLI `--theme`, or Settings tab.

Implementation: each theme module under `gui/themes/<name>.py` exports a `ThemeConfig` dataclass; `gui/app.py` applies via `ttk.Style().configure(...)` per widget class.

### 1.3 i18n: English + Simplified Chinese

- All UI strings extracted via `gettext` to `gui/i18n/en.po` and `gui/i18n/zh_CN.po`
- Locale selected via `config/settings.toml` → `ui_language` (`en` or `zh-cn`), or status-bar dropdown
- **Coverage requirement**: every English key must have a corresponding Chinese translation. CI script `gui/i18n/_coverage_check.py` fails the build if zh_CN .po has missing keys
- Exception list for un-translated proper nouns: `SST`, `STRINGS`, `EditorID`, `FormID`, `xTranslator`, `bgs-kb`, `OpenAI`, `Anthropic`, `Gemini`, `Profile`, `API key`, `TES4`, `Papyrus`, `MCM`, `VMAD`, `WEAP`, `ARMO`, etc.

### 1.4 DPI awareness and scaling

- Windows: call `ctypes.windll.shcore.SetProcessDpiAwareness(2)` at startup
- All platforms: `root.tk.call("tk", "scaling", system_dpi / 72)` to scale Tk's internal coords
- Font sizes specified in pt, not px
- Tested at 100%, 125%, 150%, 200%, 300% scaling
- Minimum window size: 1024x600 (works on netbook-class screens)

### 1.5 Keyboard + mouse

All interactions support both. No keyboard-only mode, no mouse-only mode.

Default keyboard shortcuts:
- `Ctrl+1..7` — switch tab
- `Ctrl+N` — new project
- `Ctrl+R` — refresh project status
- `Ctrl+P` — switch profile (opens picker)
- `Esc` — close current dialog
- `Tab` / `Shift+Tab` — focus cycle
- `Enter` — activate focused button / open focused row detail
- `Space` — toggle focused checkbox

All tables support arrow keys for row navigation.

### 1.6 Scrollbars

Every area that could overflow has `ttk.Scrollbar`:
- Entries table (vertical + horizontal)
- Batches list (vertical)
- Prompt preview editor (vertical)
- Logs viewer (vertical)
- Glossary table (vertical)
- All panel main content frames (vertical fallback)

---

## 2. Window layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  STATUS BAR (top, single row)                                            │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Project: adwryos-zhcn  │  Profile: openrouter-claude  │  $0.42  │    │
│  │ Lang: 中文 ▾  │  Theme: amber ▾  │  GUI alive [..]            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
├──────────────┬──────────────────────────────────────────────────────────┤
│              │                                                           │
│  NAV TREE    │  TAB BAR                                                  │
│  (left)      │  ┌──┬──┬──┬──┬──┬──┬──┐                                   │
│              │  │项│词│批│预│档│词│日│                                    │
│  ┌Projects   │  │目│条│次│览│案│表│志│                                    │
│  │ ├ adwryos │  └──┴──┴──┴──┴──┴──┴──┘                                   │
│  │ │  ├ src  │  ┌──────────────────────────────────────────────────┐    │
│  │ │  └ exp  │  │                                                  │    │
│  │ └ obliv   │  │              ACTIVE TAB CONTENT                  │    │
│  ├Profiles   │  │                                                  │    │
│  │ ├ openai  │  │                                                  │    │
│  │ └ openrtr │  │                                                  │    │
│  ├Glossary   │  │                                                  │    │
│  │ ├ vanilla │  │                                                  │    │
│  │ ├ mod     │  │                                                  │    │
│  │ ├ player  │  │                                                  │    │
│  │ └ DNT     │  │                                                  │    │
│  └Logs       │  │                                                  │    │
│              │  └──────────────────────────────────────────────────┘    │
└──────────────┴──────────────────────────────────────────────────────────┘
```

Default split: nav tree 240px wide, content area fills remainder. User-resizable via `ttk.PanedWindow`.

Status bar persists across all tabs. Nav tree is collapsible (`Ctrl+B`).

---

## 3. Seven tabs (widget detail)

### 3.1 Project tab

When a project is selected in nav tree:

**Top row**: project metadata (read-only)
```
Project: adwryos-zhcn  │  Game: Starfield  │  Source: en → Target: zh-cn
Created: 2026-06-06  │  Source plugin: adwryos.esm (SHA: a3f4...)
Active profile: openrouter-claude  │  Cost so far: $0.42 / cap $10.00
```

**Middle area**: signature counts table
```
Signature │ Total │ Translated │ Partial │ Locked │ Orphan
──────────┼───────┼────────────┼─────────┼────────┼────────
WEAP/FULL │   78  │     45     │    2    │   3    │   0
ARMO/FULL │  132  │      0     │    0    │   0    │   0
INFO/NAM1 │  412  │      0     │    0    │   0    │   0
BOOK/DESC │   12  │      0     │    0    │   0    │   0
...
```

Click a row → switch to Entries tab pre-filtered to that signature+field.

**Bottom row**: action buttons
- `[ Rescan plugin ]` — runs `xtl project rescan`
- `[ Export SST ]` — runs `xtl project export`
- `[ Open exports folder ]` — opens file manager
- `[ Project settings ]` — opens edit dialog for project.toml

**Toggle for prompt preview**: `[x] Always preview system prompt before batch dispatch` — controls whether `xtl batch run` blocks waiting for GUI approval

### 3.2 Entries tab

Read-only table view. The user does NOT edit translations here; they observe them.

**Top row**: filter widgets
- Project dropdown (which project to view)
- Signature multi-select
- Field multi-select
- Status filter: `[All] [Untranslated] [Partial] [Translated] [Locked] [Orphan]`
- Search box (substring match against EditorID + source + dest)

**Main area**: table with columns
```
FormID       │ EditorID         │ Sig:Field │ Idx │ Source              │ Dest              │ Status
─────────────┼──────────────────┼───────────┼─────┼─────────────────────┼───────────────────┼─────────
0x000A2B1C   │ Adwryo_IronSword │ WEAP/FULL │  0  │ Iron Sword          │ 铁剑              │ trans
0x000A2B1D   │ Adwryo_SteelSwd  │ WEAP/FULL │  0  │ Steel Sword         │ (untranslated)    │ untrans
...
```

Row click opens a read-only detail pane (right side, slide-out) showing full source, full dest, parent context, mask map preview.

Right-click context menu: `Copy source`, `Copy dest`, `Copy as row-id`, `Show in xTranslator (open file)` (if xTranslator install discovered).

### 3.3 Batches tab

**This is the primary monitoring surface.** Real-time updates as batches progress.

**Top row**: run selector
- Dropdown of recent runs (last 20)
- `[ Filter: in-flight only ]` toggle

**Main area**: rows per batch
```
Batch ID  │ Profile        │ Client │ Model            │ Progress   │ Tokens         │ Cost   │ Elapsed │ Status            │ Action
──────────┼────────────────┼────────┼──────────────────┼────────────┼────────────────┼────────┼─────────┼───────────────────┼──────────
b_1a3...  │ openrtr-claude │   1    │ claude-sonnet-4.5│ 40/40      │ 1240/1530      │ $0.06  │ 12.3s   │ [OK] complete     │
b_2b4...  │ openrtr-claude │   2    │ claude-sonnet-4.5│ 38/40 ▓▓▒  │ 1180 / ~1500   │ ~$0.05 │ 14.1s   │ [..] in-flight    │ [Cancel]
b_3c5...  │ openrtr-claude │   3    │ claude-sonnet-4.5│  0/40      │  0  / ~1500    │  $0.00 │  0.0s   │ [..] queued       │ [Cancel]
b_4d6...  │ openrtr-claude │   4    │ claude-sonnet-4.5│ 12/40 ▓░░  │ 380 / ~1500    │  ~$0.02│  6.7s   │ [!] retrying      │ [Cancel]
```

Each [Cancel] button cancels just that client's request. Cancellation triggers the two-stage confirmation dialog (`§4.2`).

Right side: sparkline of overall run throughput (items per second) and cumulative cost over time.

Below main area: per-run summary
```
Run rn_8af3...: 1/4 done, 3 in-flight │ items 12/160 │ $0.13 estimated │ ETA ~80s
```

[ Cancel entire run ] button at bottom (with confirmation).

### 3.4 Prompt tab

Shows the system prompt that WILL be sent (or that WAS sent) for a chosen batch.

**Top selector**:
- "Show prompt for: [next batch] [batch b_2b4...] [batch b_3c5...]"

**Main area**: text editor (`tk.Text` with monospace font + line numbers)
```
你是 Starfield (Bethesda 2023 sci-fi RPG, Settled Systems setting) 的本地化译者。

游戏世界：[agent-provided summary appears here]
mod：Adwryo's CC Spaceship Pack —— [agent-provided theme]
This is an item name for a spaceship module in a player-craftable system.

风格要求：
tone: technical-pragmatic
register: spacefaring engineer

术语表（必须严格遵循）：
- Adwryo → 阿德里奥 (character, canonical)
...

禁止翻译（保持原文）：
- Adwryo's
- $MyToken
- MCM

注意：占位符 {{P0}}, {{P1}}, ... 不要翻译、不要删除、不要增加。
返回 JSON 格式 {"I1": "译文", "I2": "译文", ...}
```

**Edit toggle**:
- `[x] Editable` — user can modify the prompt before approving
- Edits are scoped: `[O] this batch only` / `[O] this signature in this project` / `[O] this profile globally`

**Action buttons** (visible only when batch is awaiting approval):
- `[ Approve and send ]`
- `[ Approve all remaining batches in this run ]` — user's earlier-requested mode
- `[ Discard batch ]`

**Side panel**: shows the glossary subset + DNT list assembled for this batch (read-only, for verification).

### 3.5 Profiles tab

Per `09-providers-and-keys.md` §4.

Top row: list of all profiles as cards (3 per row, scrollable)

```
┌─ openai-prod ──────────┐  ┌─ anthropic-prod ───────┐  ┌─ openrouter-claude ────┐
│ openai                  │  │ anthropic               │  │ openai-compat           │
│ gpt-5-mini              │  │ claude-sonnet-4-7       │  │ anthropic/claude-...    │
│ Concurrency: 4          │  │ Concurrency: 3          │  │ Concurrency: 3          │
│ Cost: $0.00 / $5.00     │  │ Cost: $0.00 / $10.00    │  │ Cost: $0.42 / $10.00 ●  │
│ Key: [LOADED]           │  │ Key: [LOADED]           │  │ Key: [LOADED]           │
│ [Edit] [Probe] [Active] │  │ [Edit] [Probe] [Active] │  │ [Edit] [Probe] [ACTIVE] │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
```

`●` indicator on the active profile.
"ACTIVE" button replaces "Active" when this is the current default.

`[+ Add Profile]` button at top.

[Edit] opens dialog per `09-providers-and-keys.md` §4.2 — full widget detail there.

### 3.6 Glossary tab

Four sub-tabs (one per scope):
- `vanilla` (read-only display of vanilla_canon entries from packs)
- `mod` (read-only display of mod_scoped entries from packs)
- `player` (read-write; user's player_override entries)
- `do-not-translate` (read-write; user's DNT entries)

**Each sub-tab**:

Top row: filters
- Game multi-select
- Category multi-select
- Search box

Table:
```
Source           │ Target         │ Aliases      │ Category │ Source pack            │ Confidence
─────────────────┼────────────────┼──────────────┼──────────┼────────────────────────┼───────────
Whiterun         │ 白漫城         │ Whiterun's   │ place    │ bgs-kb-l10n-skyrim-... │ canonical
Daedra           │ 魔族           │              │ lore     │ bgs-kb-l10n-skyrim-... │ canonical
...
```

For writable sub-tabs (player, DNT): `[+ Add]`, `[Edit]`, `[Delete]` buttons. Add/Edit opens a dialog with all `GlossaryEntry` fields.

### 3.7 Logs tab

Real-time tail of `~/.bgs-modding-superpowers/translator/logs/YYYY-MM-DD.log`.

Filters: level (`info` / `warn` / `error`), source (`batch` / `glossary` / `sst-write` / `profile-probe` / `validator`).

Bottom row:
- `[ Pause tail ]` / `[ Resume tail ]` toggle
- `[ Open logs folder ]`
- `[ Clear filters ]`

---

## 4. Cross-cutting behaviors

### 4.1 Cross-thread comm

GUI runs on main thread (Tk). asyncio loop runs on background thread.

- GUI → backend: `event_loop.call_soon_threadsafe(asyncio.create_task, coro)` invoked from button handlers
- Backend → GUI: `update_queue` (a `queue.Queue`); GUI's `root.after(50, drain_update_queue)` polls and applies updates

Update events: `BatchProgressEvent`, `BatchCompleteEvent`, `BatchFailedEvent`, `CostUpdateEvent`, `RateLimitObservedEvent`.

### 4.2 Two-stage close

When user clicks the [X] close button or presses `Alt+F4`:

**Stage 1**:
```
┌─ Close window ─────────────────────────────────────┐
│  How do you want to close?                          │
│                                                      │
│  [Close window only]    Keep background services    │
│                         running. Batches continue.  │
│                                                      │
│  [Stop everything]      Check unsaved work, then    │
│                         cancel all batches and quit │
│                                                      │
│  [Cancel]                                            │
└─────────────────────────────────────────────────────┘
```

If "Close window only": GUI process forks a detached background process to continue the asyncio loop, then the GUI exits. (Implementation detail: on Unix, `os.fork()` + `setsid()`. On Windows, `subprocess.Popen` with detach flags.)

If "Stop everything" and there are unsaved translations or in-flight batches:

**Stage 2**:
```
┌─ Unsaved work detected ────────────────────────────┐
│  Project: adwryos-zhcn                              │
│  Unsaved translations: 42                           │
│  In-flight batches: 2 (will be cancelled)           │
│                                                      │
│  Cancellation of in-flight batches stops local      │
│  HTTP requests immediately. Provider may still bill │
│  for tokens consumed before abort. Estimated $0.05  │
│  may have been committed.                           │
│                                                      │
│  [Save SST and quit]                                │
│  [Discard and quit]                                 │
│  [Cancel]                                           │
└─────────────────────────────────────────────────────┘
```

"Save SST and quit" runs `xtl project export` for the current project, then quits.

If "Stop everything" with no unsaved work: skip stage 2, cancel any in-flight, quit.

### 4.3 Cancellation confirmation (per-batch)

When user clicks [Cancel] on a batch row in Batches tab:

```
┌─ Cancel batch client #3 ────────────────────────────┐
│                                                      │
│  Status: in-flight (32 / 40 items received)         │
│                                                      │
│  Cancellation stops the local HTTP request          │
│  immediately. The provider may have already         │
│  received and begun processing your request.        │
│  You may still be billed for tokens consumed        │
│  before the abort takes effect.                     │
│                                                      │
│  Estimated cost so far:  $0.03  [estimated, ±20%]   │
│  Profile:                openrouter-claude          │
│                                                      │
│           [Cancel anyway]    [Keep waiting]         │
│                                                      │
└─────────────────────────────────────────────────────┘
```

Per-row state after cancel:
```
b_2b4... │ openrtr-claude │ 2 │ ... │ 32/40 │ ~$0.03 │ ... │ [X] CANCELLED │ 
```

Cost in subsequent UI: marked with `~` prefix to denote estimated; OpenRouter cost-in-response calculates exact when run completes (other providers stay estimated).

### 4.4 Prompt preview IPC

When the user has "Always preview" enabled, `xtl batch run` from CLI sends an IPC request to the GUI:

```
CLI                                          GUI
 │                                             │
 │ POST /preview { batch_id, prompt, items }  │
 │ ──────────────────────────────────────────> │
 │                                             │ (GUI shows Prompt tab popup)
 │                                             │
 │                                  user clicks│
 │                                  [Approve]  │
 │                                             │
 │ Response { approved: true, edited_prompt }  │
 │ <────────────────────────────────────────── │
 │                                             │
 │ (CLI dispatches with edited prompt)         │
```

Transport: named pipe on Windows (`\\.\pipe\bgs-translator-<pid>`), Unix socket on POSIX (`/tmp/bgs-translator-<pid>.sock`).

Timeout: 5 minutes. If user doesn't respond, CLI proceeds without preview (logs warning).

If GUI is not alive (no PID file or PID file points to dead process), CLI proceeds without preview silently. The "always preview" setting is best-effort.

---

## 5. Asset paths

```
gui/
├── themes/
│   ├── amber.py
│   ├── green.py
│   └── mono.py
├── i18n/
│   ├── en.po
│   ├── en.mo
│   ├── zh_CN.po
│   ├── zh_CN.mo
│   └── _coverage_check.py
├── icons/
│   └── (none — text-based UI, no icons)
└── widgets/
    └── ... (per architecture)
```

No image assets, no icons. The aesthetic is text-only.
