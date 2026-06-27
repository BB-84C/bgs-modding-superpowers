---
id: load-order.mo2-mcp-meta-contract.v1
title: MO2 MCP _meta fields define GUI-aligned modlist and plugin order semantics
kind: rule
domains: [load-order, install-planning, file-conflicts]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Agents must use the MO2 MCP response _meta block plus per-entry section, gui_rank, and load_order_role fields for ordering and precedence claims. Do not infer MO2 left-pane or right-pane semantics from raw array index alone.
  confidence: verified-project-doc
queryKeys: [mo2-mcp _meta, Mo2Mo2Modlist_tool, Mo2Mo2Pluginlist_tool, gui_top_first, gui_rank, section, load_order_role, send_mod_to wins_over]
severity: critical
sources:
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-preflight/HANDOFF.md
    sectionPath: Tool / broker state
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-preflight/phase-B-shared-context-v2.md
    sectionPath: NEW broker contract
  - kind: project-internal-doc
    ref: .opencode/memory/45-mo2-mcp-internals.md
    sectionPath: Rule 27; GUI-Grounded Modlist/Plugins Semantics
  - kind: project-internal-doc
    ref: tools/mo2-mcp/src/tools/mo2-modlist.ts; tools/mo2-mcp/src/tools/mo2-pluginlist.ts; PR #18 commit 63c4f6c
related: [load-order.mo2-left-pane-vs-right-pane.v1, load-order.plugins-txt-vs-modlist.v1]
lastReviewed: "2026-06-27"
schemaVersion: 1
---

# MO2 MCP _meta fields define GUI-aligned modlist and plugin order semantics

## 1. Why this exists

Before MO2 MCP PR #18, agents repeatedly inverted left-pane and right-pane precedence claims because broker readouts exposed arrays in file-adjacent order without enough semantic annotation.
The agent had to remember two facts at once: `modlist.txt` is serialized in reverse GUI priority order, while `plugins.txt` is serialized in forward load order.
That convention is correct, but it is also an easy place for a fixer to make a one-line positional claim that is directionally wrong.

PR #17 fixed the full-priority-space broker semantics, PR #18 added GUI-aligned mutation vocabulary and explicit read-side `_meta` fields, and PR #19 refreshed MO2 after mutating handlers.
After PR #18 commit `63c4f6c` (2026-06-27), future positional or precedence claims must cite the live `_meta` fields and the per-entry enrichment fields instead of inferring semantics from array index.
Treat the `_meta` block as the contract that absorbs the file-format asymmetry for the agent.

## 2. Modlist `_meta` contract

`Mo2Mo2Modlist_tool` returns a `result._meta` block for the MO2 left pane.
The four load-bearing guarantees are:

1. `array_order: gui_top_first`
   - The first array entry is at the top of the MO2 GUI mods panel.
   - The last array entry is at the bottom of the MO2 GUI mods panel.
   - GUI top loses asset conflicts; GUI bottom wins asset conflicts.

2. `priority_convention: mobase_full_space_higher_wins`
   - Higher priority number means later VFS load.
   - Later VFS load wins loose-file and generated-asset conflicts.
   - Separators occupy priority slots.
   - This follows mobase `IModList.setPriority(name, priority)` semantics; it is not a non-separator-only rank.

3. `section_rule: A separator at priority X labels mods at priorities X+1..(next_higher_separator.priority - 1)`
   - A separator marks the GUI-top edge of its section.
   - Mods with higher priorities below that separator in the GUI belong to that separator until the next higher-priority separator is reached.
   - This is why separator membership must not be guessed by nearest visual distance alone.

4. Each mod object has an explicit `section` field.
   - Use `mod.section` directly.
   - Do not infer separator membership from priority distance, raw file line number, or array index.
   - `section: null` means no separator labels that mod under the current contract.

The modlist response may also expose `gui_rank` and `wins_over_count`.
Use these as annotations, but prefer the explicit `section` field for categorization claims.

### Modlist worked example

Separator `Quest Mods_separator` sits at priority `100`.
The next higher separator is priority `105`.
Under the section rule, the following four mods all belong to `Quest Mods_separator`:

| Entry | Priority | Relevant field | Meaning |
|---|---:|---|---|
| `Quest Tweaks A` | 101 | `section: "Quest Mods_separator"` | Below the separator in GUI; inside the section |
| `Quest Tweaks B` | 102 | `section: "Quest Mods_separator"` | Inside the same section |
| `Quest Tweaks C` | 103 | `section: "Quest Mods_separator"` | Inside the same section |
| `Quest Tweaks D` | 104 | `section: "Quest Mods_separator"` | Last mod before the next separator |

If a fixer report says one of these mods is outside the section, the report must show live evidence contradicting `section`.
Absent that evidence, `section` wins.

## 3. Plugins `_meta` contract

`Mo2Mo2Pluginlist_tool` returns a `result._meta` block for the MO2 right pane.
The load-bearing contract is:

1. `array_order: plugins_txt_forward_order_matches_gui`
   - The first array entry is at the top of the MO2 plugins panel.
   - The first real plugin is loaded first.
   - Loaded first means lowest record precedence and loses record conflicts.

2. The last real plugin entry is at the bottom of the GUI.
   - It is loaded last.
   - Loaded last means highest record precedence and wins record conflicts.

3. `priority` is the position in `plugins.txt` when present.
   - Higher priority number usually means later load and higher record precedence.
   - When an enriched response also exposes `load_order`, use `load_order` for effective post-sort load-index reasoning, because light plugins and engine sorting can make file position and effective load index differ.
   - For ordinary positional reports that cite `plugins.txt`, state that `priority` is the file-position value.

4. Each plugin object has `gui_rank` and `load_order_role`.
   - `gui_rank` is 1-based from the GUI top.
   - `load_order_role` is one of:
     - `loads_first_lowest_precedence`
     - `intermediate`
     - `loads_last_highest_precedence`
   - Use `load_order_role` directly when describing whether a plugin is first, last, or in the middle.

### Plugins worked example

| Plugin | Priority | `load_order_role` | Precedence meaning |
|---|---:|---|---|
| `Starfield.esm` | 0 | `loads_first_lowest_precedence` | GUI top; loaded first; loses later record overrides |
| `CommunitySystems.esm` | 50 | `intermediate` | Mid-order; can override earlier plugins and be overridden by later plugins |
| `TakeYourTimePatch.esm` | 187 | `loads_last_highest_precedence` | GUI bottom; loaded last; wins record conflicts against earlier plugins |

Do not call a plugin a winner because it appears early in the returned array.
For plugins, early array position means GUI top and lowest precedence.

## 4. Cross-pane symmetry rule

Both panes have the same user-facing rule: GUI bottom wins; the file-level fact that `modlist.txt` is reversed and `plugins.txt` is forward does not mean the panes have opposite semantics.

| | Modlist (left pane, assets) | Plugins (right pane, records) |
|---|---|---|
| GUI top | LOSES | LOSES |
| GUI bottom | WINS | WINS |
| File encoding | reversed (top of file = high priority = wins) | forward (top of file = low priority = loses) |

The asymmetry lives only in how the profile files encode position.
At the MO2 GUI and mobase layer, the mental model is consistent: lower in the pane loads later and wins.

## 5. Mutation vocabulary (PR #18)

After PR #18, `Mo2Mo2SendModTo_tool` and `Mo2Mo2SendPluginTo_tool` use GUI-aligned `target_mode` values.
Use these words instead of raw file-order phrases:

| `target_mode` | Meaning |
|---|---|
| `wins_over <anchor>` | Land directly above the anchor in GUI-facing intent terms; priority becomes anchor priority + 1, so this entry wins over the anchor. |
| `loses_to <anchor>` | Land directly below the anchor in GUI-facing intent terms; priority becomes anchor priority - 1, so this entry loses to the anchor. |
| `above_separator <name>` | Modlist organizational move relative to a target separator. Use for placing an entry around a named left-pane section boundary. |
| `below_separator <name>` | Modlist organizational move relative to a target separator. Use for placing an entry around a named left-pane section boundary. |
| `priority <N>` | Explicit numeric slot. Rare; use only when the exact priority number is the point of the operation. |
| `top` | Land at GUI top: priority 0, loses to everyone else in that pane. |
| `bottom` | Land at GUI bottom: priority max, wins over everyone else in that pane. |

For plan/apply tools, `apply` mode takes only `mode=apply`, `plan_id`, and `lease_token`.
Do not re-pass the original action arguments during apply.
The schema rejects extra apply keys with an error such as `Unrecognized key(s)`.

### Vocabulary caution

`wins_over` and `loses_to` are precedence words, not raw file-line words.
They are intentionally phrased so an agent can state the desired outcome without translating through `modlist.txt` reversal or `plugins.txt` forward encoding.

## 6. How to cite this in a fixer report

Any fixer report that makes positional, separator-membership, or precedence claims must follow this reading pattern:

1. At the top of the ordering section, cite the live broker response `_meta` block once.
   - For modlist reports, include `array_order`, `priority_convention`, and `section_rule`.
   - For plugin reports, include `array_order` and the precedence note that GUI top loads first and loses while GUI bottom loads last and wins.

2. For each mod categorization claim, cite the per-mod `section` field directly.
   - Good: `rbt_suitup_creations-cc has section: "版本已过期_separator"`.
   - Bad: `It appears near that separator, so it must belong there`.

3. For each plugin edge-position claim, cite `load_order_role` directly.
   - Good: `TakeYourTimePatch.esm has load_order_role: loads_last_highest_precedence`.
   - Bad: `It is late because I counted array rows`.

4. For mid-order plugin precedence claims, cite `priority` or `load_order` explicitly.
   - Use `priority` when the claim is about `plugins.txt` position.
   - Use `load_order` when the claim is about effective post-sort load index and the enriched response provides it.

Do not infer position from array index alone.
Array order is useful only after being interpreted through `_meta`.

## 7. Failure mode this prevents

On 2026-06-27, Lane 3 Phase B v1 sent four fan-out fixer lanes over the Starfield profile before the corrected `_meta` contract existed.
Three of the four reports misclassified separator membership or positional meaning because the v1 broker did not expose `section`, and fixers inferred membership from priority distance or raw order.
That failed especially when separator priorities were non-monotonic or when a visual cluster did not match the raw profile-file intuition.

The v2 redo used the PR #18 `_meta` block plus per-mod `section`, `gui_rank`, `wins_over_count`, and per-plugin `load_order_role`.
With those fields, the redo produced the corrected modlist and plugin audit in one pass.
The permanent rule is simple: quote the broker's semantic fields, not your memory of MO2 serialization.

## Quick checklist

- Read `_meta` before making an ordering claim.
- For left-pane categories, use `section`.
- For left-pane asset precedence, higher priority wins and separators count as priority slots.
- For right-pane record precedence, GUI top loads first and loses; GUI bottom loads last and wins.
- For plugin edge roles, use `load_order_role`.
- For mutation apply mode, pass only `mode`, `plan_id`, and `lease_token`.
- If a report depends on file-order arithmetic, rewrite it to cite GUI-aligned fields instead.
