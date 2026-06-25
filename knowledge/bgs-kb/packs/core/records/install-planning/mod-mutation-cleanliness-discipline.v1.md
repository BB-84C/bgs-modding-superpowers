---
id: install-planning.mod-mutation-cleanliness-discipline.v1
title: Clean mod mutation discipline — use mo2-mcp tools, check SC companions, document via dev-log + meta.ini
kind: rule
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: |
    A mod mutation (install / disable / enable / move / archive / drop / update) is clean only when seven disciplines are followed: tool choice (use mo2-mcp tools, not raw bash), folder-name vs plugin-name separation (modlist uses folder names; plugins.txt uses .esm/.esp filenames; never conflate), SC companion sweep (every mod operation must check for `<name> - SC` / `<name> 汉化` / locale-variant companions), pre-mutation dev-log entry (intent + rollback path), meta.ini comments (status marker visible in MO2 GUI mod list), dependency check (other mods that require this one), and conflict check (xEdit override + asset overlay impact). Skipping any of the seven produces visible bugs the curator catches within seconds.
  confidence: high
queryKeys:
  - mod mutation discipline
  - clean mutation workflow
  - mo2-mcp tools vs bash
  - SC companion search
  - localization companion
  - 汉化 companion
  - folder name vs plugin name
  - phantom modlist entry
  - meta.ini comments status
  - dev-log mutation entry
  - dependency check mutation
  - rollback mutation
  - mod archive workflow
severity: high
sources:
  - kind: project-internal-doc
    ref: BB84 2026-06-25 audit correction — agent used raw bash to edit modlist.txt with plugin name DenserVegetationGterra; created phantom entry because actual mod folder name is Denser Vegetation - GRiNDTerra; left SC companions untouched on both Denser and OwlTech archives; user caught both failures within seconds
related:
  - install-planning.audit-workflow-rigor.v1
  - install-planning.mod-update-post-state-discipline.v1
  - engine.mo2-process-locking-semantics.v1
lastReviewed: "2026-06-25"
schemaVersion: 1
---

# Clean mod mutation discipline — use mo2-mcp tools, check SC companions, document via dev-log + meta.ini

## Perspective: OBJECTIVE

A mod mutation in a curated MO2 modpack — install, disable, enable, move between separators, archive, drop, update — is a small action with a wide blast radius. It touches mod folders, modlist.txt ordering, plugins.txt activation, meta.ini metadata, dependency chains, localization companions, and the curator's mental model of "what is installed and why". Cutting corners on any one of these dimensions produces visible bugs the curator catches within seconds.

Seven disciplines define clean mutation. Skipping one is the failure pattern this rule exists to prevent.

## 1. Tool choice — mo2-mcp tools, not raw bash

mo2-mcp tools enforce structural correctness that raw filesystem edits cannot. They know the difference between mod folder names (used in modlist.txt) and plugin filenames (used in plugins.txt), so a `mo2_toggle_mod name="Foo"` call cannot create a phantom entry the way `(Get-Content modlist.txt) -replace '\+FooBar', '-FooBar'` can. They run a plan/apply pattern with lease tokens, so concurrent operations cannot stomp on each other. They emit audit trails that bash edits never produce.

The cost of using mo2-mcp tools is a slightly more verbose call pattern. The cost of bypassing them is the phantom-entry class of bug that surfaces only when the curator opens MO2 and notices nothing changed. The trade decisively favors mo2-mcp for mutations.

Use raw bash only when mo2-mcp is genuinely unavailable for the specific operation (sidecar implementation gap, permission ceiling not raised, or a one-off read-only diagnostic). When falling back to bash, the rules in disciplines 2-7 still apply.

## 2. Folder name vs plugin name separation

The two name surfaces are NOT interchangeable:

- **MO2 modlist.txt** uses mod **folder** names. A folder can be named with spaces, mixed case, Chinese characters, dashes, parentheses, and any other filesystem-legal pattern. Example: `Denser Vegetation - GRiNDTerra`.
- **plugins.txt** uses **plugin filenames** (`.esm` / `.esp` / `.esl`). These are constrained by Bethesda plugin naming conventions and usually less expressive. Example: `DenserVegetationGterra.esm`.

The same mod is referenced by different strings in the two files. Conflating them is the source of the phantom-entry class of bug: an agent searches modlist.txt for `+DenserVegetationGterra`, finds nothing, creates `-DenserVegetationGterra` as a new entry believing it disabled the mod, while the actual mod sits untouched at line 59 as `+Denser Vegetation - GRiNDTerra`. The phantom entry then appears in MO2 as an invalid mod reference, and the real mod stays enabled.

Before editing modlist.txt, the correct folder name MUST come from disk verification:

```powershell
Get-ChildItem -LiteralPath "<MO2Root>/mods" -Directory | Where-Object { $_.Name -like "*<keyword>*" }
```

Or, better, from a mo2-mcp `mo2_modlist` query that returns the authoritative inventory. The mo2-mcp tools handle this correctly because they operate on folder names by design.

## 3. SC companion sweep

In a curated non-English locale modpack, most mods have a localization companion — typically named `<original mod name> - SC` (Simplified Chinese) or `<original mod name> 汉化` or similar. The companion mod is a sibling folder that overrides specific assets (strings files, sometimes the .esm itself) to localize the parent.

Every mod operation must sweep for the companion. Disabling a parent mod without disabling its SC companion leaves the SC companion as an orphan — it has nothing to translate, it may load a stale ESM, and it confuses the GUI display ("why is `<mod> - SC` enabled when `<mod>` is in 弃用?"). Conversely, enabling a parent without enabling its SC silently degrades the localization the curator expects.

The sweep pattern:

```text
For every mutation target T:
  1. Look for "<T> - SC" — same priority class, sibling localization mod
  2. Look for "<T> 汉化" — alternative localization companion naming
  3. Look for any mod with the same root .esm file (locale variants often share ESM names but override strings via .strings/.dlstrings/.ilstrings)
  4. Apply the same mutation to every companion found
  5. Surface the companion list to the curator if the mutation crosses a decision boundary
```

When the parent mod has localization companions, the meta.ini comment on the parent should reference them, and vice versa, so future maintenance can trace the bundle.

## 4. Pre-mutation dev-log entry

Before any mutation that changes the modpack's enabled set, write to `<MO2Root>/docs/dev-log.md`:

- Intent — what is being changed and why
- Scope — which mod folders, which plugins, which separators
- Replacement — if the action is drop / archive, what (if anything) replaces the functionality
- Rollback path — the backup file path, the commit hash, the steps to undo
- Authorization — the user's verbatim decision or the audit verdict that triggered the mutation

A mutation without a dev-log entry is invisible six months later. The dev-log is the audit trail; meta.ini comments are the at-a-glance status markers; together they make the modpack maintainable.

## 5. meta.ini comments — at-a-glance status markers

The MO2 GUI mod list shows the `meta.ini` `[General] comments=` field in a column. After every mutation that changes a mod's status, update the comment to reflect the new state with a structured marker:

- `[ARCHIVED <date>] superseded by <new mod> #<modid>` — for archive-on-replace
- `[DROPPED <date>] curator decision; <reason>` — for drop without replacement
- `[WAITING-FOR-<runtime>]` — for mods sitting in 等待作者更新 separator
- `[VERSION-TAG-UNSYNC]` — for Nexus page-version desync cases
- `[UPDATE→vX]` — for in-progress update queue markers

These markers are how the curator scans the mod list. A mod in 版本已过期 separator with an empty `comments=` field is a future-debt mystery: "why is this archived?" If the comment says `[ARCHIVED 2026-06-25] superseded by Vanilla Biomes Enhanced #16176`, the curator can re-derive the decision in five seconds.

## 6. Dependency check

Before disabling / archiving / dropping a mod, check what depends on it:

- xEdit `references` query — what other mods load this mod as a master
- modlist entry inspection — patches or compatibility add-ons named `<target> - <X> Patch` or `<X> x <target> Compat`
- meta.ini `requirements=` field of every other mod for back-references

A mod with active dependents cannot be cleanly dropped without dropping or migrating the dependents first. Surface the dependency tree to the curator before the mutation, not after.

## 7. Conflict check

Before installing or enabling a new mod, check what it conflicts with:

- xEdit conflict-audit on the new mod against the current load order (see `xedit-conflict-audit`)
- Asset overlay overlap against the MO2 conflict report
- Author description's "incompatible with" list

A clean install includes a conflict-check pass that the curator can review before the mutation lands.

## Anti-pattern that triggered this rule

In the 2026-06-25 BB84 Starfield audit closeout, the agent disabled and archived two mods using raw bash file edits. Two failures resulted within minutes:

1. The Denser Vegetation - GRiNDTerra mutation created a phantom `-DenserVegetationGterra` entry in modlist.txt because the agent used the plugin filename (`DenserVegetationGterra.esm` → stripped suffix) instead of the actual mod folder name (`Denser Vegetation - GRiNDTerra`). The real mod stayed enabled at its original position.
2. Both Denser Vegetation and OwlTech_Pathfinder mutations left their SC companion mods (`Denser Vegetation - SC`, `OwlTech_Pathfinder - SC`) untouched, leaving them as orphaned localization mods after the parent was archived.

Both failures would have been impossible with mo2-mcp `mo2_toggle_mod` (which uses authoritative folder names) plus an SC-companion sweep step (which is now codified here). The cost of doing it correctly the first time is a few additional tool calls; the cost of the failures is curator trust + agent re-work.

## See also

- `install-planning.audit-workflow-rigor.v1` — the six audit-grade disciplines; mutation cleanliness is the action-time complement to audit-time rigor.
- `install-planning.mod-update-post-state-discipline.v1` — intent-vs-effect discipline at the audit / post-mutation observation level.
- `engine.mo2-process-locking-semantics.v1` — when MO2 must be closed vs not; clean mutation must also respect process locks correctly.
- `mod-evaluation.investigating-pulled-mods.v1` — continuity tracing precedes archive-and-replace mutation.
