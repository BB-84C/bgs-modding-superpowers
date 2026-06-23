# Source-mined extraction: Asset precedence judgment for `using-bgs-archive`

Sources:
- `[E12]` = `F:\my clip\FO4\MOD Tutorial\E12\Fallout 4 Mod整合搭建教程.txt`
- `[E10]` = `F:\my clip\FO4\MOD Tutorial\E10\1.txt`
- `[cv]` = `.opencode/artifacts/sixiang-sources/articles/cv21859652.txt`
- `[opus]` = `.opencode/artifacts/sixiang-sources/articles/opus_813053196219973664.txt`
- `[architecture]` = `docs/internal/plans/2026-06-23-sixiang-judgment-layer-architecture.md`

## 1. What asset precedence is (FRAMEWORK)

Asset precedence is the question: when two mods provide the same runtime asset path, which bytes does the game actually read?

- Loose files and packed archive entries are both projected into the game `Data` path by the mod manager. The curator must reason about the final projected path, not the source container. `[E12]` names the basic learning target as game mod file structure, common suffixes, where they act in the game path, and the mod sorting principle.
- Loose-vs-archive priority is cross-game framework knowledge: loose assets win over archive content at the same virtual path. The requested skill body should teach this as a framework rule, not as a Fallout 4-only exception. `[architecture]`
- Archive-to-archive order is not the same decision as MO2 left-pane loose-file order. Archive loading is tied to the plugin/load-order surface (`plugins.txt` / right-pane plugin ordering), because BGS archives are discovered through plugin-associated archive names. `[cv]` uses the final blank ESP ordering as the last step of its BA2 consolidation workflow; `[architecture]` locks the rule as "archive load order is determined by plugins.txt, not by mod order in MO2."
- Practical BB84 framing: before trying more advanced conflict surgery, first understand BA2/BSA and loose files. `[E10]` explicitly says new users should first get BA2 and loose files straight before worrying about Edit.

## 2. Asset precedence vs plugin-load-order (RELATED but DIFFERENT)

Asset precedence and plugin record load order interact, but they are not the same layer.

| Layer | What it decides | Common false move | Source |
|---|---|---|---|
| Asset precedence | Which mesh/texture/script/interface file path wins | Blame plugin order for a wrong texture/model | `[architecture]`, `[E10]` |
| Plugin load order | Which record override wins in xEdit / runtime data | Repack/extract assets to fix a record conflict | `[E12]`, `[E10]` |
| Archive ordering | Which archive entry wins among packed providers | Drag left-pane mod order and expect packed assets to change | `[cv]`, `[architecture]` |
| Loose override | Whether a loose file masks all packed copies at the same path | Leave accidental extraction output active and misdiagnose the archive | `[cv]` workflow extracts loose assets deliberately, then hides originals |

The important judgment move is to identify the layer first. A wrong record value needs xEdit conflict reasoning; a wrong asset file needs final virtual-file-tree reasoning.

## 3. When to extract loose vs leave packed (trade-off FRAMEWORK)

Extracting loose is not inherently cleaner and packing is not inherently safer. It is a trade-off:

- Extract loose when the operational question is "which exact asset path is winning?" or when a controlled loose override is the least confusing proof. Keep it bounded and staged in an MO2 overlay/workspace, never game `Data`. `[cv]`
- Leave packed when the archive count and loading behavior are not the problem, because needless extraction creates duplicate file surfaces and makes future conflict reading harder. `[cv]` explicitly warns its workflow causes file redundancy and suggests starting from small archives to reduce duplicated-file cost.
- If the issue is a game-specific archive ceiling / startup CTD class, do not hard-code a recipe in the archive skill. Query the KB and follow the game-specific diagnostic record. `[cv]`, `[architecture]`
- For FO4-specific precombine/previs or BA2-ceiling reasoning, the skill should point to `bgs_kb_query`, not carry the facts inline. `[architecture]`

`[GAP]`: The provided sources do not give a cross-game numeric archive-count threshold, a universal repacking cutoff, or a universal "extract these folders first" rule. Treat any such number as game-specific KB content, not skill content.

## 4. Red flags (thought -> reality, FRAMEWORK)

| Thought | Reality | Source |
|---|---|---|
| "The wrong texture/model loaded, so I should move ESPs around." | First inspect asset precedence: loose files and archives can decide the bytes independently of record order. | `[architecture]`, `[E10]` |
| "MO2 left pane controls everything." | Left-pane loose-file priority and archive order are different surfaces; packed archives follow plugin/load-order rules. | `[architecture]`, `[cv]` |
| "Extracting all BA2/BSA files loose will make conflicts easier." | It may create duplicate active surfaces and make diagnosis noisier; extraction is a bounded diagnostic or workaround, not a default lifestyle. | `[cv]` |
| "If an archive is hidden, the replacement is automatically safe." | Read back the final virtual paths; hiding/repacking can change which assets are reachable and can produce model/texture errors. | `[cv]` final in-game walkaround check |
| "Precombine/previs is an archive problem." | That is game-engine-specific record/visibility behavior; query the KB instead of turning the archive skill into a FO4 essay. | `[architecture]`, `[E10]`, `[opus]` |

## 5. Rationalizations (excuse -> reality, FRAMEWORK)

| Excuse | Reality | Source |
|---|---|---|
| "I will just unpack everything and sort it out later." | Later-you inherits duplicate files and a noisier virtual tree; unpack only the bounded asset set you need to prove. | `[cv]` |
| "The plugin order changed, so the asset order must have changed." | Maybe for plugin-associated archives, but not for loose files; inspect the final asset provider chain. | `[architecture]` |
| "The file is inside a BA2, so MO2 mod priority is irrelevant." | The archive still enters through the load-order surface; archive decisions are load-order-adjacent even when the content is not a record. | `[cv]`, `[architecture]` |
| "This is just textures, it cannot be a real conflict." | Asset conflicts are real runtime behavior; a texture/mesh/interface file can be the entire visible bug. | `[E12]` file-structure emphasis |
| "FO4 has a known recipe, so put it directly in the archive skill." | The architecture says game facts live in KB; skill carries the judgment frame and queries KB on demand. | `[architecture]` |

## 6. Skill-section content to inject

The injected `using-bgs-archive` section should be game-agnostic and compact:

1. Overview: asset precedence is the final provider decision for runtime asset paths.
2. Rules: loose beats archive; archive order comes from `plugins.txt` / plugin load order, not MO2 mod order.
3. KB discipline: before applying FO4 precombine/previs or BA2-ceiling reasoning, run `bgs_kb_query` with Fallout4 + `archive-precedence` / `engine`; do not inline the facts.
4. Red-flags table and rationalizations table.
5. Handoff: after asset precedence is understood, route record-level conflicts to `xedit-conflict-audit`.

## 7. Game-specific facts -> KB (NOT skill content)

- FO4 precombine/previs: already authored in `knowledge/bgs-kb/packs/bgs-kb-fallout4/records/fo4-previs/precombines-and-previs-are-one-minefield.v1.md`. Skill should query, not inline. `[architecture]`, `[E10]`, `[opus]`
- FO4 BA2 ceiling / CTD class: already authored in `knowledge/bgs-kb/packs/bgs-kb-fallout4/records/fo4-previs/ba2-file-limit-ctd.v1.md`. Skill should query, not inline. `[architecture]`, `[cv]`
- Testing and diagnosis cues for these FO4 cases belong in KB and runtime workflows, not in the archive skill body.

`[GAP]`: Sources are FO4-heavy. Cross-game archive precedence framework is locked by the architecture spec, but per-game caveats for Skyrim/Starfield archive ordering or engine-specific asset edge cases were not source-mined in this batch.
