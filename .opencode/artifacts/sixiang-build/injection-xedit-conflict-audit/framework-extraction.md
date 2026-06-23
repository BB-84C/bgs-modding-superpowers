# Source-mined extraction: xEdit conflict judgment injection

Sources:
- `[E9]` = `F:\my clip\FO4\MOD Tutorial\E9\FO4Edit与Creation Engine数据结构讲解.txt`
- `[E12]` = `F:\my clip\FO4\MOD Tutorial\E12\Fallout 4 Mod整合搭建教程.txt`
- `[bv5]` = `.opencode/artifacts/sixiang-sources/bilibili/05-fo4-mod-logic-fo4edit-guide.txt`

## Decision axes

| Axis | Extracted judgment | Source + anchor |
|---|---|---|
| Intentional override / accept | Accept an override when the later record is deliberately the rule you want and the earlier change can be lost without breaking the pack's intended behavior. This is not "no conflict"; it is a chosen winner. | `[E12]` "让后面更重要的覆盖它们的数据" |
| Ordering error / reorder | Reorder when one mod expresses the broader systemic rule and the losing edit is only an incidental author tweak. Let the systemic-rule mod win before creating patch debt. | `[E12]` "系统性修改插槽的模组装在后面" |
| Selective forwarding / patch | Patch when multiple mods have needed fields on the same FormID and sorting would only choose one side. Sorting is a single-choice lever; patching is the way to carry needed data forward. | `[E9]` "调整排序永远是在做单选题"; `[bv5]` "我们想全都要" |
| Patch hygiene | Make a new override patch instead of dragging data into the current winner. Directly editing the winning mod creates later cleanup debt; a patch can be disabled. | `[E9]` "直接修改了最右边模组的数据"; `[bv5]` "取消补丁加载" |
| ITM / clean | Treat copied vanilla records as cleaning candidates: E9 defines unchanged copied records as green, but does not provide a full cleaning policy. | `[E9]` "复制了原版的记录而未作任何修改"; `[GAP — needs user input]` exact clean/delete policy beyond ITM identification |
| Remove mod | Remove/reject only when the conflict audit shows the mod's required data is not needed for this pack or its role cannot justify patch/reorder cost. The corpus supports discarding unneeded data, but not a hard mod-removal threshold. | `[E12]` "哪些数据可以不要"; `[GAP — needs user input]` removal threshold and save-safety policy |
| Diagnose before acting | Data overlap itself is normal. Only conflicts tied to actual broken behavior deserve intervention. | `[E12]` "大多数情况下的数据冲突都是正常的"; `[E12]` "导致游戏出问题的数据" |
| Think from actual environment | Whether a field should be forwarded is situational: source meaning + actual mod environment + desired behavior, not a universal rule. | `[E9]` "实际模组环境"; `[bv5]` "数据有没有必要让它生效" |
| Scale tiebreaker | "xEdit can patch anything" is true in principle and false as a pack-scale operating plan. Use order to reduce patch surface, then patch only what matters. | `[E12]` "一个个Form ID去做缝补，是根本不现实的" |

## Red flags (thought → reality)

| Thought | Reality | Source + anchor |
|---|---|---|
| "Red means broken; fix every red cell." | Red means overlapping data. Most data conflicts are normal; chase behavior-breaking conflicts. | `[E9]` "它们的数据相互冲突"; `[E12]` "大多数情况下的数据冲突都是正常的" |
| "Just reorder until both changes work." | Reordering is a single-choice lever. It cannot make two different same-row values both win. | `[E9]` "调整排序永远是在做单选题" |
| "The rightmost value wins, so the rest is irrelevant." | Earlier columns are reference evidence. They show lost data you may need to forward. | `[E9]` "展现给你的参考罢了" |
| "I'll drag the field into the winning mod." | That mutates the mod you are trying to evaluate and creates later deletion debt. | `[E9]` "一条一条数据地删除" |
| "xEdit can patch everything, so order doesn't matter." | True in principle; impossible at real FormID scale. Use order to reduce patch workload. | `[E12]` "数十万条Form ID" |
| "The conflict is visible in xEdit, so xEdit alone tells the whole story." | Some errors are not visible as wrong data; scripts or presentation may require other tools. | `[E12]` "用xEdit看不出来" |

## Rationalizations (excuse → reality)

| Excuse | Reality | Source + anchor |
|---|---|---|
| "Sorting is easier; I'll avoid patches." | Sorting chooses A or B. If needed fields live on both sides, the result is still loss. | `[E9]` "要么让A模组生效" |
| "I'll patch all conflicts now so future me is safe." | Patch only data that matters; exhaustive FormID stitching is not realistic. | `[E12]` "一个个Form ID去做缝补" |
| "The later mod is new, so its override must be intended." | Later means winner, not automatically correct. Compare meaning against pack need. | `[E9]` "最右边的模组是优先级最高"; `[E9]` "根据自己的需求" |
| "The earlier field disappeared but the game still boots." | Lost data can silently disable features; booting is not semantic success. | `[E9]` "功能不生效" |
| "I know what this field does from the label." | Some names are abstract; learn purpose from CK wiki, examples, and actual use. | `[E9]` "数据名字比较抽象" |
| "If it is not visibly crashing, accept it." | The target is coherent behavior, not just no crash. Find the data causing the actual problem. | `[E12]` "导致游戏出问题的数据" |

## Hand-off to xedit-automation

When this decision gate returns `PATCH`, stop the conflict-audit workflow. Hand the focused record(s), intended winning semantics, and forwarded fields to `xedit-automation`; conflict audit should decide that a patch is needed, not author the patch here. `[E9]` "制作补丁的方法"; `[E12]` "数据兼容操作".
