# MO2 MCP — GUI-aligned semantics for modlist/plugins tools

**Status**: PROPOSED — awaiting user approval
**Filed**: 2026-06-27
**Triggered by**: User report — "我现在怀疑你所有处理modlist的mo2 mcp tools都是有逻辑问题的" (after orchestrator-delta misinterpreted section ownership twice in one session despite being told modlist.txt is reversed)
**Related**: `docs/issues/BUG-mo2-mcp-send_mod_to-semantics-2026-06-27.md` (already fixed in PR #17 at the broker validator level; this plan addresses the API surface)

## Core problem

The mo2-mcp tool surface forces agents to do mental gymnastics:

1. **`modlist.txt` is REVERSED** (top of file = priority N-1 = wins = bottom of MO2 GUI).
2. **`plugins.txt` is FORWARD** (top of file = loads first = loses = top of MO2 GUI).
3. Same parameter words (`top`/`bottom`/`above`/`below`/`priority`) mean OPPOSITE things between the two files.
4. A separator at priority X labels mods at priorities X+1..next_higher_sep-1 (= visually BELOW the separator header in MO2 GUI). No tool surfaces this; agents compute it (wrongly, often).
5. `priority` int alone has no direction label in any response.

Tool author bias compounded this: `mo2_send_mod_to` modes are named in terms of mobase priority direction (`top` = priority N-1 = wins), not MO2 GUI direction (`top` = visually top = loses). Curators and agents both default to GUI mental model. Result: wrong-section placements, repeat confusion, real bug (issue 2026-06-27).

## Design principle

**Agent-facing semantics MUST mirror MO2 GUI.** Internal implementation can use mobase priority freely; the surface layer translates.

Vocabulary contract (will be documented in every tool):

| Concept | Term | Maps to mobase |
|---|---|---|
| Visually top of MO2 GUI mods panel | `gui_top` | priority 0 |
| Visually bottom of MO2 GUI mods panel | `gui_bottom` | priority N-1 |
| Mod A wins over Mod B in conflicts | A `wins_over` B | A.priority > B.priority |
| Mod A loses to Mod B in conflicts | A `loses_to` B | A.priority < B.priority |
| Section labeled by separator S | mods at S.priority+1..next_higher_sep-1 | "below S in GUI" |

Verbs `wins_over` / `loses_to` are unambiguous because they describe **precedence semantics**, not visual direction. They map cleanly to either GUI or mobase priority without needing to know either convention.

## Scope decisions (load-bearing — please confirm)

### D1. Backward compatibility for renamed modes

**Recommendation: Soft-deprecate (Option B).** Accept old mode names; route them through new logic; emit a `deprecation_warnings: [...]` array in the response so agents see the alternative.

- Option A (hard break): cleaner, but every agent prompt that uses `top`/`bottom`/`above_separator` breaks at next session.
- **Option B (alias + warn)**: old names keep working, new names preferred. Migration is gradual.
- Option C (keep both forever): no migration pressure, technical debt forever.

`[override→ A / C]`

### D2. Mode-name scheme for `mo2_send_mod_to`

**Recommendation: Verb-based.** Use `wins_over` / `loses_to` / `gui_top` / `gui_bottom` / `raw_priority`. Separator semantics emerge naturally: `wins_over: <separator_name>` = mod ends up at sep.priority+1 = inside section labeled by separator at its top-visual position (this is what curators normally want).

Alternative: explicit section modes (`into_section_top` / `into_section_bottom`). More verbose but spells out intent.

`[override→ explicit-section-modes / hybrid (both)]`

### D3. Order of `mo2_modlist` returned array

Current: modlist.txt file order = high-priority first = GUI BOTTOM first.

**Recommendation: Keep file order, ADD `gui_rank` field per mod + clear `_meta.direction` block.** Changing array order is a hard break for downstream consumers (curator-side scripts, KB queries, etc.).

Alternative: reverse to GUI-top-first. Cleaner mental model, breaks compat.

`[override→ reverse-to-gui-order]`

### D4. Add new tool `mo2_send_plugin_to`?

Currently no tool reorders plugins (only toggles). Adding this rounds out the surface symmetrically with `mo2_send_mod_to`. Maps to broker `plugins.set_priority` (already exists) + new `plugins.set_load_order` wrapper.

**Recommendation: Include in this PR.** Same vocabulary applies (gui_top/gui_bottom/wins_over/loses_to), but for plugins.txt direction (forward file order), `gui_top` = priority 0 = top of file = loads first.

`[override→ defer to followup PR]`

### D5. Fix real footguns in same PR

- `mo2_install target_priority: int` is accepted by schema but silently ignored. Route through send_mod_to-style priority adjustment.
- `mo2_reinstall_mod` doesn't auto-register new plugins like `mo2_install` does. Add `_registerPluginsInPluginsTxt` to reinstall apply path.

**Recommendation: Yes, include both.** They're the same class of bug (tool surface lies about what it does).

`[override→ defer]`

## Tool-by-tool change list

### `mo2_send_mod_to` — major redesign

**New modes (preferred):**
```typescript
target_mode:
  | "gui_top"             // priority 0 (loses everything)
  | "gui_bottom"          // priority N-1 (wins everything)
  | "wins_over"           // requires `anchor: <mod-or-separator-name>` → anchor.priority + 1
  | "loses_to"            // requires `anchor: <mod-or-separator-name>` → anchor.priority - 1
  | "wins_over_conflicts" // priority = max(conflict_pris) + 1
  | "loses_to_conflicts"  // priority = min(conflict_pris) - 1
  | "raw_priority"        // requires `priority: number`, clamped [0, mod_count-1]
```

**Aliases (deprecated, still work):**
```typescript
top                  → gui_bottom (priority N-1)   [DEPRECATED: name suggests GUI top, actually GUI bottom]
bottom               → gui_top    (priority 0)     [DEPRECATED: name suggests GUI bottom, actually GUI top]
priority             → raw_priority                [DEPRECATED: name lacks direction hint]
above_separator      → wins_over (separator)       [DEPRECATED: "above" was ambiguous; was actually placing INSIDE the section]
above_first_conflict → wins_over_conflicts         [DEPRECATED: "first" was ambiguous]
below_last_conflict  → loses_to_conflicts          [DEPRECATED: "last" was ambiguous]
```

Plan diff string upgrade: `${name}: → priority 395 (wins over 版本已过期_separator, inside its section)` instead of `→ priority 395 (mode=above_separator)`.

Response envelope gains:
```typescript
_meta: {
  priority_convention: "mobase_full_space_higher_wins",
  modlist_file_order: "reverse_of_gui",
  gui_direction_hint: "priority_0_at_gui_top_loses; priority_N-1_at_gui_bottom_wins"
}
```

### `mo2_modlist` — read-side additions (non-breaking)

Per-mod new fields:
```typescript
mods[].section: string | null  // name of separator labeling this mod (null if mod is above all separators)
mods[].gui_rank: number        // 1-indexed from GUI top (priority 0 = rank 1, priority N-1 = rank N)
mods[].wins_over_count: number // count of mods this mod overrides (priority - 1 for non-edge)
```

Response-level new fields:
```typescript
_meta: {
  array_order: "modlist_file_order_high_priority_first",
  array_order_note: "First entry has highest priority = wins everything = visually at BOTTOM of MO2 GUI mods panel",
  section_rule: "A separator at priority X labels mods at priorities X+1..next_higher_sep-1"
}
```

### `mo2_pluginlist` — read-side clarification (non-breaking)

Per-plugin new fields (when enriched):
```typescript
plugins[].load_order_role: "loaded_first_low_precedence" | "..." // direction label
plugins[].gui_rank: number    // 1-indexed from GUI top (top of plugins.txt = rank 1 = loads first = loses)
```

Response-level:
```typescript
_meta: {
  array_order: "plugins_txt_forward_order",
  array_order_note: "First entry loads first = lowest precedence = visually at TOP of MO2 GUI plugins panel; LAST entry wins all plugin conflicts",
  priority_vs_load_order: "priority = position in plugins.txt; load_order = effective post-sort load index (differs when ESL/light/master interleave)"
}
```

### `mo2_create_mod` + `mo2_create_separator` — alias

`above: X` → still works, becomes alias for `wins_over: X`. Deprecation warning in response.

New explicit shape:
```typescript
anchor: { mode: "wins_over" | "loses_to" | "gui_top" | "gui_bottom", target?: string }
```

### `mo2_install` — fix footgun + align

- Accept `target_priority` as `"gui_top" | "gui_bottom" | "top"(deprecated) | "bottom"(deprecated) | number`
- For numeric `target_priority`, ACTUALLY route through priority adjustment (currently silently ignored)
- Response gains `final_priority: number` so agent doesn't have to re-query

### `mo2_reinstall_mod` — plugin auto-register parity

- Add `_registerPluginsInPluginsTxt` call to apply path (mirror `mo2_install` BUG-E fix)
- Add `plugins_registered: string[]` to response
- Note in description that reinstall now matches install for plugin registration

### `mo2_send_plugin_to` — NEW TOOL (if D4=yes)

Symmetric to mo2_send_mod_to but for plugins. Internal implementation calls broker `plugins.set_priority` (already exists).

Modes:
```typescript
target_mode:
  | "gui_top"             // priority 0 / top of plugins.txt / loaded first / loses
  | "gui_bottom"          // priority N-1 / bottom of plugins.txt / loaded last / wins
  | "wins_over"           // anchor.priority + 1
  | "loses_to"            // anchor.priority - 1
  | "raw_priority"
```

### All tools — `_meta.direction_contract` block

Universal addendum on every priority-touching response. Single source of truth for direction semantics. Eliminates need for agents to remember which file is forward vs reversed.

## Implementation phases

### Phase 1 — Read-side additions (no behavior change, non-breaking)

1. Add `section` / `gui_rank` / `wins_over_count` to `mo2_modlist`
2. Add `gui_rank` / `load_order_role` to `mo2_pluginlist`
3. Add `_meta.direction_contract` to read tool responses
4. Tests: assert new fields present and consistent with mobase priority

### Phase 2 — Write-side new modes (non-breaking — old modes still work)

1. Add new `target_mode` enum values to `mo2_send_mod_to` schema
2. Implement `wins_over` / `loses_to` / `gui_top` / `gui_bottom` / `wins_over_conflicts` / `loses_to_conflicts` / `raw_priority`
3. Keep old modes; route them through new modes; emit `deprecation_warnings`
4. Plan diff string includes semantic explanation
5. Same for `mo2_create_mod`, `mo2_create_separator` `above` → `wins_over`
6. Tests: new modes produce correct priorities; old modes still work; deprecation warning surfaces

### Phase 3 — Fix real footguns

1. `mo2_install target_priority: int` actually works
2. `mo2_install` accepts `gui_top` / `gui_bottom` (with `top` / `bottom` deprecation)
3. `mo2_reinstall_mod` auto-registers new plugins
4. Tests: integer placement works end-to-end; reinstall with new plugin lands in plugins.txt

### Phase 4 — New tool (if D4=yes)

1. `mo2_send_plugin_to` with GUI-aligned modes
2. Plan/apply pattern matching `mo2_send_mod_to`
3. Tests + acceptance fixture

### Phase 5 — Documentation + memory

1. Update memory rule `45-mo2-mcp-internals.md`: add a "vocabulary contract" rule documenting GUI-aligned semantics
2. Update tool docstrings (all priority-touching tools) with GUI direction note + link to vocabulary contract
3. Update `docs/issues/BUG-mo2-mcp-send_mod_to-semantics-2026-06-27.md` with resolution note pointing to this PR

## Acceptance plan

**Semantic acceptance (vitest)** — required to merge:
- Each new mode in `mo2_send_mod_to` produces correct priority for the user's actual BB84 Starfield fixture (12-mod / 4-separator synthetic + real-data integration test)
- `section` field on `mo2_modlist` matches manual computation against the corrected rule
- `gui_rank` field is consistent with mobase priority (rank = priority + 1 since GUI top = priority 0)
- `mo2_install` with integer `target_priority` lands the mod at that priority
- `mo2_reinstall_mod` with new plugin in the archive auto-registers it in plugins.txt
- Deprecated mode names still work and emit `deprecation_warnings`

**Live acceptance against `D:\Starfield MO2`** — required after Phase 2:
- `mo2_send_mod_to wins_over: 版本已过期_separator` for some test mod → readback confirms mod inside 版本已过期 section (priorities 395+)
- `mo2_send_mod_to loses_to: 版本已过期_separator` for some test mod → readback confirms mod just below separator in priority = OUTSIDE section, visually above separator header in GUI
- `mo2_modlist` returns `section: "观望_separator"` for Real Fuel - BETA - SC (priority 384, in 观望 section)
- `mo2_send_mod_to gui_top` → priority 0
- `mo2_send_mod_to gui_bottom` → priority N-1

## Risks

1. **Bigger PR than usual.** ~6 tool surfaces touched + 1 potential new tool + memory rule. Mitigation: clean phase split (read-side first as independent commit).
2. **Backward-compat aliases add code surface.** Mitigation: aliases live in a single normalization function, easy to remove later.
3. **Existing tests may need updates for changed plan diff strings.** Mitigation: update tests as part of each phase.
4. **`_meta` blocks may bloat response sizes** for read tools that return long arrays. Mitigation: `_meta` is response-level (single block), not per-entry.
5. **Agents already trained on old vocabulary may resist new modes.** Mitigation: deprecation warnings teach the new vocab naturally over a few sessions.

## Out of scope (explicit non-goals)

- Renaming `priority` field itself across the codebase (would require broker change; high risk)
- Changing modlist.txt or plugins.txt file format (we're not MO2)
- New conflict tools surfacing provider chain ordering at TS layer (a separate concern; the conflict tools work, just opaque)
- Plugins.txt reordering at SCALE (`plugins.set_load_order` broker handler exists but has no TS wrapper; adding it is a nice-to-have, separate from `mo2_send_plugin_to`)
- Renaming sidecar's `provider_chain` field shape

## Decision summary requested from user

Five load-bearing decisions, each with a recommendation marked:

1. **D1 backward compat**: soft-deprecate (recommended) / hard break / coexist
2. **D2 mode scheme**: verb-based `wins_over`/`loses_to` (recommended) / explicit section modes / hybrid
3. **D3 array order**: keep file order + add `gui_rank` (recommended) / reverse to GUI order
4. **D4 add `mo2_send_plugin_to`**: yes, include in this PR (recommended) / defer to followup
5. **D5 fix install + reinstall footguns**: yes, include (recommended) / defer

Once confirmed, I'll execute on a feature branch in 5 phases per the implementation section above, with semantic acceptance against BB84's profile after Phase 2 + Phase 3.
