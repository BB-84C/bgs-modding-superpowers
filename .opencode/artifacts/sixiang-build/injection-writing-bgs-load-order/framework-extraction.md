# Source-mined extraction: load-order sorting judgment injection

Sources:
- `[E3]` = `F:\my clip\FO4\MOD Tutorial\E3\New Text Document.txt` (Vortex-era sorting fundamentals; extract principle only)
- `[E12]` = `F:\my clip\FO4\MOD Tutorial\E12\Fallout 4 Mod整合搭建教程.txt` (cross-stage 总纲 + xEdit 终极奥义)
- `[bv11]` = `.opencode/artifacts/sixiang-sources/bilibili/11-fo4-load-order-principles.txt` (AI subtitle of favlist #11)

## What sort actually does

- Sorting changes which plugin data the game reads for overlapping records: for any FormID, the game reads the data from the last-loaded plugin that contains that FormID. `[E12]` anchor: "对于任何一条Form ID，游戏都只会读最后包含此Form id 的模组中的数据".
- The same later-wins rule applies to archive-backed assets: if plugin A loads before plugin B, A's BA2 loads before B's BA2, and B's BA2 wins on archive conflicts. `[E3]` anchor: "A mod的插件在B之前读取的话...A的BA2文件也会在B的BA2文件之前加载...最终决定文件的是B的BA2文件". `[bv11]` anchor: "它插件在B模组之前读取的话...最终决定文件的是B模组的BA2文件".
- Loose-file conflicts are separate from plugin order: loose files load after BA2 files and win over archive contents; ordinary loose-file overwrite choice can be independent from plugin order. `[E3]` anchor: "文件夹的覆盖是独立于插件的排序的" and "游戏永远是先加载所有的BA2文件，然后才会加载散文件...最终决定覆盖的，是散文件". `[bv11]` anchor: "文件夹的覆盖是独立于插件的排序" and "如果BA2文件和散文件之间有冲突...最终决定覆盖的是来自散文件的那一份".
- Sorting therefore propagates through the visible game state: it is not cosmetic list cleanup. Bad order can surface as FPS drops, bugs, or crashes, while some mods may simply be incompatible no matter where they sit. `[E3]` anchor: "掉了十几二十帧，那就说明mod的排序出了问题，或者是这个mod根本就不能和你已有的mod兼容".

## Ordering principles

- Use groups to make order manageable at pack scale: assign mods into purpose-based groups, then order the groups so batches move together instead of making every plugin a one-off micro-rule. `[E3]` anchor: "提前把插件分到对应的组里，然后给组排序，就可以批量化地管理mod的排序". `[bv11]` anchor: "提前把插件分到对应的组里，然后给组排序就可以批量化的管理模组的排序".
- A good group should mostly contain mods that do not fight each other; same-category items can coexist when they add independent content, but same-group exceptions still need explicit before/after reasoning. `[E3]` anchor: "同一个组里的mod是应该不存在冲突的...但也有一个分组中，某两个mod需要特别设定前后依赖关系". `[bv11]` anchor: "同一个分组里的模组应该是不存在冲突的...也会出现在同一个分组中某两个模组需要特别设定前后依赖关系".
- Masters and official early-loading plugins are not a creative sorting surface; they must load early / be inferred from the runtime. Existing skill source plus corpus principle: user-managed order starts after early masters; do not hardcode per-game lists. `[E12]` supports the generic later-wins model, anchor: "最后包含此Form id"; existing skill already sources official-master mechanics to libloadorder/MO2/xEdit.
- Patches belong late when their purpose is to carry the final stitched decision. `[E12]` anchor: "把来自多个模组的数据缝补到一起，然后把兼容补丁放最后加载就行了".
- Prefer the later winner that expresses the pack's systemic rule over incidental edits from a content mod. `[E12]` anchor: "系统性修改原版装备插槽的模组装在后面...目的就是要所有装备使用的插槽有一个系统的规则".
- Lighting/weather/USSEP-style group positioning is a per-game template question, not a game-agnostic skill fact. `[GAP]` The mined corpus says to create researched groups and order them, but does not provide a stable cross-game lighting/weather/USSEP placement rule. Store/retrieve those templates from KB, not from this skill.

## Sort-vs-patch decision (the BB84 "终极奥义")

- The theoretical endpoint is: order does not matter if every conflicting FormID is patched into one final winning compatibility patch. `[E12]` anchor: "排序其实根本不重要...使用xEdit可以把前面任意包含此Form ID的数据搬运到最后".
- The practical endpoint is the opposite: exhaustive per-FormID stitching is impossible at real pack scale, so a sane ordering structure reduces the patch workload. `[E12]` anchor: "至少数十万条Form ID...一个个Form ID去做缝补，是根本不现实的" and "在这个基础上来做数据缝补，会减少很多工作量".
- Sort when the desired outcome can be expressed as "this mod's record/archive should win wholesale over that one." `[E12]` anchor: "完全可以让后面更重要的覆盖它们的数据".
- Patch when the desired outcome is a data stitch that no linear order can express: keep fields from multiple mods in one final record. `[E12]` anchor: "把来自多个模组的数据缝补到一起".
- Use xEdit to see the conflict the manager cannot show. `[E12]` anchor: "游戏里具体某个数据是否存在Mod冲突，是在管理器界面看不出来的...要用xEdit加载所有的模组列表".

## LOOT vs manual sort

- Beginner-safe default: if the author gives no special instruction, leave order alone or use the manager's automatic sort. `[E12]` anchor: "排序都很简单，那就是不管它，除非Mod作者有特别说明，或者使用管理器自带的自动排序".
- Automatic sort is a starting point, not judgment: E3 calls Vortex automatic sorting unintelligent and less directly controllable than MO2 micro-ordering. `[E3]` anchor: "这种自动排序相当不智能" and "MO2显然更灵活". `[bv11]` anchor: "这种自动排序相当的不智能".
- Manual sort is appropriate when a specific winner is known, a group boundary is wrong, author instructions require ordering, or xEdit readback shows the automatic result does not express the desired data. `[E3]` anchor: "某两个mod需要特别设定前后依赖关系". `[E12]` anchor: "实际操作中是需要大家自己去判断，哪些数据可以不要，哪些数据是需要的".
- `[GAP]` LOOT-specific metadata groups and per-game group templates are not discussed in the mined sources. Treat LOOT here as the automatic-sort class already represented in the existing skill; query KB for per-game LOOT/group templates before naming positions.

## Red flags (thought → reality)

| Thought | Reality | Source |
|---|---|---|
| "排序无所谓，xEdit能补一切" | True only in principle; stitching tens/hundreds of thousands of FormIDs is not realistic. | `[E12]` "一个个Form ID去做缝补，是根本不现实的" |
| "管理器自动排序了，所以不用判断" | Automatic sort is a baseline, not intelligence; it can need group/order overrides. | `[E3]` "这种自动排序相当不智能" |
| "同类模组随便放，都是一个分组" | Same-group conflicts still need explicit before/after decisions. | `[E3]` "某两个mod需要特别设定前后依赖关系" |
| "BA2/loose assets follow the same rule as plugin records" | BA2 follows plugin order, but loose files are a separate later-winning layer. | `[E3]` "BA2文件...依赖于mod的插件排序" + "散文件" wins |
| "管理器界面没冲突，所以没冲突" | Record-level conflicts are visible in xEdit, not the manager list. | `[E12]` "在管理器界面看不出来...要用xEdit" |
| "Lower/higher order is a style preference" | Sort selects real winning data and can affect bugs, crashes, and performance. | `[E3]` "排序出了问题，或者...不能...兼容" |

## Rationalizations

| Excuse | Reality | Source |
|---|---|---|
| "I'll just patch everything later." | Patch everything is the impossible endgame; order first to reduce the patch surface. | `[E12]` "数十万条Form ID...不现实" |
| "LOOT / auto-sort is enough for every user." | Auto-sort is acceptable for beginners, but mature packs require judgment and xEdit readback. | `[E12]` "萌新这个阶段" + `[E3]` "自动排序相当不智能" |
| "The latest content mod should win; it adds the new thing." | A systemic-rule mod may need to win over incidental vanilla edits from content mods. | `[E12]` "系统性修改插槽的模组装在后面" |
| "I can decide group order from vibes." | E3's group order is presented as researched and proven by long pack testing, not vibes. | `[E3]` "自己研究过后整理出来的分组以及它们的前后顺序" |
| "If two mods are incompatible, sorting harder will fix it." | Some conflicts are order problems; some mods simply cannot coexist. | `[E3]` "排序出了问题，或者...根本就不能...兼容" |
| "Archive conflicts are invisible, so ignore them." | Invisibility is exactly why BA2-vs-loose and plugin-order precedence must be understood. | `[E3]` "玩家无法看到具体是什么文件冲突" |

## [GAP] markers

- `[GAP]` No source-mined per-game group template for lighting/weather/USSEP-style placement; defer to future `load-order` KB records.
- `[GAP]` No LOOT-specific metadata/editing guidance in the mined corpus; only the broader automatic-sort-vs-manual-judgment principle is sourced.
