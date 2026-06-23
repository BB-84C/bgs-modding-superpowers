# Source-mined extraction: BB84's whole-pack curation judgment

Sources:
- `[E12]` = `F:\my clip\FO4\MOD Tutorial\E12\Fallout 4 Mod整合搭建教程.txt` (GB18030; cross-game 总纲 / 思想论)
- `[introBL]` = `F:\my clip\FO4\废土蓝调整合\介绍\New Text Document.txt` (GB18030; 废土蓝调整合 intro and declared style)
- `[BL2]` = `F:\my clip\FO4\废土蓝调整合\2.0\1.txt` (GB18030; 2.0 devlog and lessons)
- `[BB84-philosophy]` = `F:\my clip\Bethesda Breakdown\Bethesda_设计理念报告_视频稿完整版_BB84风格.txt` (GB18030; systems-simulation framing)
- `[bv2]` = `.opencode/artifacts/sixiang-sources/bilibili/02-bgs-modpack-ultimate-guide-crossgame.txt` (UTF-8 AI subtitle; captured transcript is unrelated fitness content, treated as unusable)
- `[bv12]` = `.opencode/artifacts/sixiang-sources/bilibili/12-fo4-beginner-prep.txt` (UTF-8 AI subtitle; naming/category discipline)

Cross-reference instead of re-extracting: `.opencode/artifacts/sixiang-build/evaluating-bgs-mods/framework-extraction.md` §1 already captures the systems-simulation / 风格 / co-authorship lens used by per-mod evaluation.

## 1. What "curating a pack" means

| Point | Source | Anchor quote |
|---|---|---|
| Curating is building a personal game world through many mods, not installing four or five conveniences. | `[E12]` | "想要通过多个模组来构建一套专属于自己个人的游戏世界" |
| The whole-pack question starts from 思想论, not tool mechanics. | `[E12]` | "本视频为全系列最重要的部分，即系列的思想论部分" / "主要重点在于思想论，而非方法论" |
| Stability is only the entry threshold; the pack's 风格 is the soul. | `[E12]` | "一个稳定，没有什么问题的整合...仅仅只是...门槛" / "整合包整体的风格才是灵魂所在" |
| 风格 must be explicit and memorable; different styles are not ranked, but undeclared style cannot guide decisions. | `[E12]` | "不同的风格之间没有高低贵贱" / "只有明确、独特的风格，才能被更多玩家所记住" |
| Modpack building is co-authorship in BGS's open platform, not a pile of patches over a broken official game. | `[BB84-philosophy]` | "Mod不是'玩家帮BGS补锅'，而是'BGS邀请玩家共建'" |
| The curator's work is to preserve systemic feedback and behavior traceability across the whole pack. | `[BB84-philosophy]` | "搭一个系统，然后让故事自己发生" / "沉浸感不是'演技感人'，而是'行为可追踪'" |
| A pack can and should announce who it is for by naming its style before listing its contents. | `[introBL]` | "重要的问题是，这款整合包的风格，是你想要玩的那种吗？" |
| A concrete declared style can reject individually attractive mods that do not belong. | `[introBL]` | "完全没有任何酷炫战术风格，COD风格，或者塔可夫风格的枪，因为它们的风格不是这个整合想要的东西" |
| The invisible work behind a pack is optimization, compatibility, naming, categories, and system integration, not just the visible mod list. | `[introBL]` / `[BL2]` | `[introBL]` "你们看不到的地方...游戏的优化和模组兼容"; `[BL2]` "汉化名词统一...分类规则...等级列表的融合、平衡...数据以及关键词的兼容" |
| `[GAP]` The corpus does not give a numeric batch size, release cadence, or exact rollback interval. | `[GAP]` | Source is principle-heavy; no "install N mods per batch" rule appears. |

## 2. Quality signals for a pack

| Signal | Source | Anchor quote |
|---|---|---|
| The pack can state its 风格 before the feature list. | `[E12]` / `[introBL]` | `[E12]` "我到底想要制作一款什么风格的整合"; `[introBL]` "这个整合包，到底适不适合我？...风格" |
| The pack can explain each content area as a role in the whole vision, not as a count flex. | `[introBL]` | "内容主要包括四个大方面：武器、剧情、世界观、和游戏性" |
| The pack has a coherent naming and grouping system so future debugging does not depend on memory. | `[E12]` | "对刚安装的模组进行体系化的重命名" / "几百个mod...岂不是头都要大了" |
| Patch naming preserves ownership and parent relationship. | `[bv12]` | "盒子世界补丁...这是不能接受的" / "方便你以后的排错，以及确保禁用这个mod的时候不会漏掉什么东西" |
| Local archives, tags, plugin groups, and mod-manager categories use aligned names. | `[bv12]` | "文件夹的命名，应该与你给mod分配的标签命名相同" / "压缩包的文件命名应该与你之前的重命名相同" |
| The curator can articulate why every mod exists and which style/system role it serves. | `[E12]` | "默认mod名字极其简陋...花多少时间来回忆这个mod具体是起什么作用" |
| Attribution is explicit: community authors and translators are named rather than absorbed into the pack brand. | `[introBL]` / `[BL2]` | `[introBL]` "感谢社区模组制作者们的无私奉献...特别感谢B站Up主Big Stan"; `[BL2]` "感谢辐射4社区所有的模组作者" |
| External paid/third-party components are not repackaged silently; the pack may provide configuration while telling the user to support the author. | `[BL2]` | "只预留了空文件...保留了DLSS的参数配置文件...赞助作者并安装模组" |
| Honest expectation-setting is a quality signal: the curator reports imperfect state rather than overpromising. | `[BL2]` | "希望大家有个合理的期待" / "整合包仍然有很多不完美的地方" |
| `[GAP]` The sources do not define a universal separator taxonomy beyond systematic naming/categories; exact separator templates remain curator/project policy. | `[GAP]` | Source gives naming/category principles, not a fixed separator grammar. |

## 3. Risk signals

| Risk | Source | Anchor quote |
|---|---|---|
| 风格 drift: adding good-looking content that does not support the declared style. | `[introBL]` | "风格不是这个整合想要的东西" |
| Stability-as-finish-line: thinking a booting/stable pack is already a good pack. | `[E12]` | "稳定...仅仅只是...门槛" |
| Stage-2 over-confidence: after learning tools, the curator thinks they already understand the ecosystem. | `[E12]` | "产生一种'我觉得我行了'的幻觉" |
| Scale risk: too many mechanics-changing or story/content mods can overwhelm a new curator's ability to reason about interactions. | `[E12]` | "尽量装那种比较简单的武器，服装类模组，不要装过多的修改游戏机制的模组，剧情模组也少装一些" |
| Brittle rollback: disabling recent mods is not safe for every stack, especially script-heavy mods. | `[E12]` | "关闭掉一些带有脚本的Mod反而会引发更严重的问题" |
| Exhaustive patching fantasy: xEdit can technically reconcile records, but whole-pack scale makes one-by-one repair unrealistic. | `[E12]` | "数十万条Form ID，一个个Form ID去做缝补，是根本不现实" |
| Overpromising on stability/FPS without enough play coverage is a credibility and QA failure. | `[BL2]` | "吹了一个大牛...完全是来自我当时对整合包游玩不够充分的无知" |
| Perfectionism can kill the release instead of improving it. | `[BL2]` | "如果为了追求绝对的完美，那可能整合包最后直接就烂尾" |
| Unattributed bundling / rehosting erases authorship and install evidence. | `[introBL]` / `[BL2]` | `[introBL]` "本整合的一切模组来自于社区"; `[BL2]` "赞助作者并安装模组" |
| `[GAP]` The sources do not prescribe exact save-break thresholds, script-count thresholds, or rollback automation mechanics. | `[GAP]` | Source warns qualitatively; game-specific mechanics belong in KB. |

## 4. Fit signals

| Signal | Source | Anchor quote |
|---|---|---|
| The pack's first decision is "what style am I making?"; later mod choices are judged against that axis. | `[E12]` | "我到底想要制作一款什么风格的整合" |
| The pack states who will enjoy it and who probably will not. | `[introBL]` | "这款整合包，到底适不适合我？" / "大概率会觉得无聊" |
| Additions are grouped into coherent roles such as weapons, story/worldbuilding, environment, survival/combat, optimization, compatibility. | `[introBL]` / `[BL2]` | `[introBL]` "武器、剧情、世界观、和游戏性"; `[BL2]` "汉化名词统一...分类规则...等级列表...兼容" |
| Batching should create rollback boundaries around recent additions because the first diagnostic ladder is "recent batch off, then binary search". | `[E12]` | "直接关闭最近装的几个模组；如果还没用，那就上二分法" |
| Batching must be conservative around script-heavy mods because disabling is not equivalent to rollback. | `[E12]` | "关闭掉一些带有脚本的Mod反而会引发更严重的问题" |
| Devlog discipline matters: honest logs turn painful discoveries into future tutorial/tooling knowledge. | `[BL2]` | "中间也学到了很多新的东西，这些东西也或多或少被我转化成了教程分享给大家" |
| Naming, category, and separator discipline are not bureaucracy; they are future diagnostic leverage. | `[E12]` / `[bv12]` | `[E12]` "每次多花一点点的时间...日后的整合构建工作顺心不少"; `[bv12]` "方便你以后的排错" |
| A pack can reserve external mod slots/configs while respecting authorship, instead of pretending third-party dependencies are first-party pack assets. | `[BL2]` | "预留了空文件...赞助作者并安装模组" |
| `[GAP]` The source does not state whether batch boundaries should map to MO2 separators, Git commits, save checkpoints, profile clones, or all of the above. | `[GAP]` | Implementation surface is absent; skill should route to devlog + tool skills rather than inventing one. |

## 5. Red flags

| Thought | Reality | Source |
|---|---|---|
| "稳定 = 整合包做完了." | Stable/no obvious problems is only the floor; 风格 is the soul. | `[E12]` "仅仅只是...门槛" / "风格才是灵魂" |
| "风格 can wait until after I add enough mods." | Without declared 风格, the pack has no fit axis and no way to reject attractive noise. | `[E12]` "我到底想要制作一款什么风格的整合" |
| "This cool gun/story/mechanic is good, so it belongs." | Good-in-isolation is not pack-fit if it drifts from the declared style. | `[introBL]` "风格不是这个整合想要的东西" |
| "I learned sorting/xEdit; I am basically done learning." | Stage 2 creates the documented "我觉得我行了" illusion. | `[E12]` "保持谦虚" / "我觉得我行了的幻觉" |
| "Disable the latest mods; rollback solved." | Script-heavy mods can make disabling worse; rollback boundaries must be planned before adding risk. | `[E12]` "关闭掉一些带有脚本的Mod反而会引发更严重的问题" |
| "Patch everything in xEdit later." | Whole-pack FormID volume makes exhaustive patching impractical. | `[E12]` "一个个Form ID去做缝补，是根本不现实" |
| "The pack can claim no crashes / 60 FPS everywhere." | BB84 explicitly walked back this overpromise as insufficient play coverage. | `[BL2]` "游玩不够充分的无知" |
| "No need to name/separate; I remember what this mod is." | Future debugging over hundreds of mixed-name mods depends on naming discipline. | `[E12]` "花多少时间来回忆这个mod具体是起什么作用" |

## 6. Rationalizations

| Excuse | Reality | Source |
|---|---|---|
| "Naming and separators are admin work; real work is installing." | Naming/categories are what make later troubleshooting possible. | `[E12]` "体系化的重命名" / `[bv12]` "方便你以后的排错" |
| "I can install a big batch now and diagnose later." | Recent-batch rollback and binary search only work if the batch boundary is coherent and reversible. | `[E12]` "最近装的几个模组...二分法" |
| "Script mods are fine; a mod manager can disable anything." | Script-heavy mods may break worse when disabled mid-save. | `[E12]` "脚本的Mod...更严重的问题" |
| "If the pack is stable, the style will reveal itself." | 风格 is a deliberate answer, not an emergent byproduct of stability. | `[E12]` "风格才是灵魂所在" |
| "Users want more stuff; a bigger list is a better pack." | The corpus frames the pack as a world/style/system, not a feature count. | `[E12]` "专属于自己个人的游戏世界" / `[introBL]` "风格" |
| "I'll make it perfect before release." | Absolute perfection risks abandonment; honest closure can be better than 烂尾. | `[BL2]` "绝对的完美...直接就烂尾" |
| "If a paid/third-party dependency matters, bundle around it." | Respect authorship: reserve configuration, direct users to support/install the author-provided component. | `[BL2]` "赞助作者并安装模组" |
| "The AI subtitle should confirm E12." | The captured `[bv2]` subtitle is unrelated fitness content and cannot support modpack claims. | `[bv2]` "五分化...训练强度" |

## 7. Game-specific facts to KB

| Fact area | Source | KB routing |
|---|---|---|
| Fallout 4 archive/previs/precombine scale risk and BA2 ceiling handling. | `[E12]` says FO4 has precombine-specific optimization; existing KB already carries FO4 BA2/archive/previs facts. Anchor: "预组合这个系统". | Keep game-specific numbers/tool steps out of the skill; query `archive-precedence`, `engine`, and `install-planning` for Fallout4. |
| Skyrim animation / behavior / LOD ecosystem scale risk. | `[E12]` names DynDOLOD and Nemesis as Skyrim-specific tools. Anchor: "上古卷轴5会需要用到 DnydoLOD...复仇女神". | KB per-game records under `engine`, `tooling.*`, or `install-planning`; skill only says query for game-specific ecosystem risks. |
| Starfield toolchain and engine facts are evolving and must be re-grounded. | `[E12]` speaks from 2023 forecast. Anchor: "星空嘛，我们拭目以待" / "目前暂时不清楚". | KB variants for Starfield; mark old source claims as historical/low-confidence unless re-reviewed. |
| Cross-game load order vs patching principle. | `[E12]` anchor: "排序根本不重要" in principle, then "一个个Form ID去做缝补...不现实" at scale. | Core KB can capture the principle; per-game KB should hold practical tooling differences. |
| Save safety / script uninstall risk. | `[E12]` anchor: "脚本的Mod...更严重的问题". | Core `save-file` / `install-planning` record could hold cross-game principle; per-game variants should describe script extender/runtime differences. |
| Pack curation batching framework. | `[E12]` recent-batch/binary-search + `[BL2]` devlog lessons + `[bv12]` naming discipline. | Authored as optional core KB record `pack-curation.incremental-batching.v1.md` because the principle is cross-game and not tied to a single skill body. |
