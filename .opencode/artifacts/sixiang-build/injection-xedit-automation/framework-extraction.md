# Source-mined extraction: Patch Authoring Judgment injection

Scope: new `## 补丁创作判断 / Patch authoring judgment` section for `skills/xedit-automation/SKILL.md`.

Sources:

- `[E9-GBK]` = `F:\my clip\FO4\MOD Tutorial\E9\FO4Edit与Creation Engine数据结构讲解.txt` decoded as GB18030.
- `[E12-GBK]` = `F:\my clip\FO4\MOD Tutorial\E12\Fallout 4 Mod整合搭建教程.txt` decoded as GB18030.
- `[E9-bili]` = `.opencode/artifacts/sixiang-sources/bilibili/05-fo4-mod-logic-fo4edit-guide.txt`.
- `[Hub-existing]` = pre-existing `skills/xedit-automation/SKILL.md` hard-ban text before this injection.

## Authoring axes

| Axis | Judgment extracted | Source anchor |
|---|---|---|
| Forward winners, not losers, when stacking patches | The game reads the rightmost/winning override for a FormID; left-side data is reference material until intentionally forwarded. A patch should start from the current winner, then forward only the required upstream values so the patch does not regress fields already won by the current rightmost record. | `[E9-bili]` lines 172-188: game reads the rightmost data; left-side edits not carried by the rightmost winner do not reach the game. `[E9-GBK]` lines 299-319: rightmost data wins; left-side B data in a field A did not carry is not read. `[E9-bili]` lines 267-273: new patch initially copies the rightmost data, then receives only desired compatibility data. |
| Sorting is single-choice; patching is all-we-need, but not all-the-things | Reordering chooses A or B; it cannot make both mods' field values active. Patching can combine values, but exhaustive per-FormID stitching is not realistic at pack scale, so the author must choose which values matter. | `[E9-bili]` lines 213-220: sorting cannot make two edits active; it is a single-choice problem. `[E12-GBK]` lines 1039-1079: in principle any FormID can be stitched in xEdit, but hundreds of thousands of FormIDs make one-by-one patching unrealistic. |
| Never copy unchanged values into the patch | xEdit's green/unchanged-copy state means copied original with no modification; carrying those forward creates ITM-style noise rather than intent. A patch should contain meaningful compatibility edits, not cloned baseline values. | `[E9-bili]` lines 165-170 and `[E9-GBK]` lines 287-289: green means copied original/vanilla record and no changes. `[GAP]` BB84 describes the state but does not use the term `ITM`; mapping green unchanged copies to ITM/noise is xEdit vocabulary. |
| Preserve references before deleting records | Do not delete or mark-deleted a record without checking incoming references. | `[GAP]` The BB84 E9/E12 corpus here explains Add/Remove on tree data but does not provide a referenced-by deletion rule. `[Hub-existing]` line 178 already carries the MCP safety rule: do not delete/mark-deleted referenced records without `records.referenced_by`. |
| ESL/master-order discipline | For compatibility patches, BB84 prefers an ESP flagged ESL over native ESL/ESM when possible: it avoids occupying a full plugin slot while remaining sortable among ESPs. Native ESL/ESM loads at the front and cannot be sorted among normal ESPs. | `[E9-bili]` lines 235-260 and `[E9-GBK]` lines 393-433: option three creates an ESP read as ESL; ESP/ESM slots are scarce; native ESL/ESM is forced early; ESL-flagged ESP remains sortable among ESPs. |
| Override vs new record | Corpus strongly covers override patches for existing FormIDs: copy as override into a new patch, not direct-edit the winning source mod. | `[E9-bili]` lines 221-275 and `[E9-GBK]` lines 361-459: direct-dragging into the rightmost mod is discouraged because reversal requires manual deletion; copy-as-override into a new file keeps the source mod untouched and reversible. `[GAP]` The corpus does not provide a general rule for when to create a net-new record instead of overriding an existing FormID. |
| Good patch vs band-aid patch | A good patch is a reversible, separate compatibility layer that preserves the current winner and forwards only intentional values after understanding what the data means. A band-aid patch directly edits the source mod, blindly drags fields because red exists, or attempts to stitch every FormID because sorting “doesn't matter.” | `[E9-bili]` lines 223-275: direct source edits are discouraged; new patch can be disabled if reversed. `[E9-bili]` lines 293-305 and 378-389: knowing what to drag and whether it should take effect requires analysis in the actual mod environment. `[E12-GBK]` lines 1061-1079 and 1081-1113: exhaustive stitching is impractical; decide which data matters, with systemic-rule edits beating incidental personal tweaks. |
| Read the data structure, not the color alone | Red means at least two mods conflict on that row, but color is only the start. The author must inspect the record tree and field meaning, using CK wiki/community examples when necessary, then decide what compatibility is needed. | `[E9-bili]` lines 155-170 and `[E9-GBK]` lines 271-289: use Legend to understand colors. `[E9-bili]` lines 349-389 and `[E9-GBK]` lines 589-657: records are tree data; field names may require CK wiki or observed mod examples; compatibility depends on actual need and mod environment. |
| Overlap tiebreaker | When a mod's core FormIDs matter but it also tweaks an incidental vanilla field, let a systemic rule mod win the incidental field if the pack goal is a unified rule. | `[E12-GBK]` lines 1087-1113: new equipment records matter most to the equipment mod; vanilla body-slot tweak may be author personal thought; a systemic slot-rule mod can load later because the goal is unified rules. |

## Red flags (thought -> reality)

| Thought | Reality | Source |
|---|---|---|
| "It's red, so copy the left value into my patch." | Red only says there is overlap. Whether the value should survive requires reading the field meaning and the actual mod environment. | `[E9-bili]` lines 155-170, 293-305, 378-389. |
| "The rightmost mod is wrong; I'll edit it directly." | Direct-editing the source mod destroys reversibility. Copy as override into a new patch so reversal is disabling/removing the patch, not hand-deleting fields from the mod. | `[E9-bili]` lines 221-275; `[E9-GBK]` lines 361-459. |
| "If sorting can be arbitrary after patching, I'll patch every conflict." | That is true only in principle. Real games contain hundreds of thousands of FormIDs; exhaustive stitching is not realistic. | `[E12-GBK]` lines 1039-1079. |
| "Green records in my patch are harmless." | Green unchanged copies are not intent; BB84 describes them as copied originals with no modification. They are ITM-style noise unless removed or justified. | `[E9-bili]` lines 165-170; `[E9-GBK]` lines 287-289. |
| "Native ESL is cleaner than an ESP flagged ESL." | Native ESL/ESM loads at the front and loses normal ESP sorting freedom; BB84 prefers ESL-flagged ESP for ordinary patch plugins. | `[E9-bili]` lines 235-260; `[E9-GBK]` lines 393-433. |
| "This record looks unused; delete it." | `[GAP]` BB84 source here does not discuss referenced-by deletion safety. Existing xEdit automation doctrine requires checking incoming references first. | `[Hub-existing]` line 178. |

## Rationalizations (excuse -> reality)

| Excuse | Reality | Source |
|---|---|---|
| "I'll just drag the value into the winning mod; it is only one field." | That makes the source mod itself the patch. If you change your mind, cleanup becomes one-by-one deletion; a separate override patch is the reversible shape. | `[E9-bili]` lines 221-275; `[E9-GBK]` lines 361-459. |
| "Sorting doesn't matter because xEdit can fix anything." | xEdit can stitch FormID data in principle, but patching every record across a real pack is impossible as a working method. Use sorting to reduce repair debt, then patch the meaningful remaining conflicts. | `[E12-GBK]` lines 1039-1079. |
| "The patch should preserve everything any mod touched." | The right question is which values matter. BB84's example lets a systemic body-slot rule override an incidental vanilla body-slot tweak because the pack wants one consistent rule. | `[E12-GBK]` lines 1087-1113. |
| "The field name is abstract, so I'll copy what looks plausible." | Abstract field names are a research signal: check the Creation Engine wiki or learn from real mod examples, then decide in the actual mod environment. | `[E9-bili]` lines 349-389; `[E9-GBK]` lines 637-657. |
| "I can leave the patch in overwrite; MO2 sees it." | BB84 calls moving it into a separate mod folder a good habit; a patch is a managed mod, not unmanaged spill. | `[E9-bili]` lines 285-293; `[E9-GBK]` lines 477-493. |
| "If I copy the whole winning override first, the patch is automatically good." | Copying the winner is only the starting layer. The good patch begins when intentional compatibility values are forwarded and unchanged clones/noise are removed. | `[E9-bili]` lines 267-273 plus lines 293-305; `[E9-GBK]` lines 443-453 plus 501-509. |

## Sources cited

- `F:\my clip\FO4\MOD Tutorial\E9\FO4Edit与Creation Engine数据结构讲解.txt` (`[E9-GBK]`, GB18030 decoded): line ranges 271-289, 299-319, 361-459, 477-493, 589-657.
- `F:\my clip\FO4\MOD Tutorial\E12\Fallout 4 Mod整合搭建教程.txt` (`[E12-GBK]`, GB18030 decoded): line ranges 1039-1113.
- `.opencode/artifacts/sixiang-sources/bilibili/05-fo4-mod-logic-fo4edit-guide.txt` (`[E9-bili]`): line ranges 155-170, 172-188, 213-275, 285-305, 349-389.
- `skills/xedit-automation/SKILL.md` pre-existing hard ban (`[Hub-existing]`): line 178.

## GAP markers

- `[GAP]` BB84 source describes unchanged copied records/green state but does not use the term `ITM`.
- `[GAP]` BB84 source is silent on referenced-by deletion discipline; retained from existing xEdit MCP safety doctrine.
- `[GAP]` BB84 source covers override patches for existing FormIDs but not a general override-vs-new-record decision rule.
