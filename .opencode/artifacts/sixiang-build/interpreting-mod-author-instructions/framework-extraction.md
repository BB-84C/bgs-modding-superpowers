# Source-mined extraction: interpreting mod-author install instructions

Sources:
- `[E2]` = `F:\my clip\FO4\MOD Tutorial\E2\New Text Document.txt` (install-flow fundamentals; Vortex-era clicks discarded)
- `[E12]` = `F:\my clip\FO4\MOD Tutorial\E12\Fallout 4 Mod整合搭建教程.txt` (cross-game modding posture / author说明 emphasis)
- `[E11]` = `F:\my clip\FO4\MOD Tutorial\E11\1.txt` (MO2 instance/profile/tool posture)
- `[bv3]` = `.opencode/artifacts/sixiang-sources/bilibili/03-fo4-mo2-advanced.txt` (AI subtitle; near-empty)
- `[bv9]` = `.opencode/artifacts/sixiang-sources/bilibili/09-fo4-fallui-suite.txt` (AI subtitle; near-empty)
- `[bv12]` = `.opencode/artifacts/sixiang-sources/bilibili/12-fo4-beginner-prep.txt` (AI subtitle version of E2)

## 1. What good install means (FRAMEWORK)

- Good install begins with author-intent comprehension, not manager-button execution. `[E12]` "仔细看作者说明"
- The installer must know whether the mod can be installed, how, and with what consequences. `[E12]` "能不能装，怎么装，装了会有什么后果"
- The manager-specific UI can change; the underlying install thought stays portable across managers. `[E2]` "操作上会有不同，但是思路是一样的"
- A good install preserves traceability from local mod entry back to the original mod page. `[E2]` "引导你回到这个mod的n网网页"
- A good install keeps main files, patches, translations, and compatibility pieces named so future debugging can reconstruct the relationship. `[E2]` "后续的排错"
- A good install uses the correct MO2 instance/profile/tool context so tools see the modded game view, not the naked game directory. `[E11]` "如果不通过mo2启动"
- A good install leaves a rollback path before making local changes. `[E11]` "创建备份"

`[GAP — needs user input]`: corpus does not provide a universal FOMOD option taxonomy, per-option decision tree, or variant naming standard beyond "read the author's instructions".

## 2. Quality signals for instructions (FRAMEWORK)

| Signal | Source | Anchor |
|---|---|---|
| Original page/source preferred because it carries the fullest说明 surface | `[E12]` | "N网上mod说明的信息量是最充足的" |
| Rehosted files without detailed说明 are lower-quality install sources | `[E12]` | "很少会把作者的说明详细的搬运过来" |
| English instructions are valid; the curator must translate and understand them | `[E12]` | "哪怕用翻译软件机翻" |
| Instructions that state requirements, install order, and consequences are the useful surface | `[E12]` | "怎么装，装了会有什么后果" |
| A flow that links the installed entry back to the author page is higher quality | `[E2]` | "方便你查看和确认" |
| Local naming/category discipline is part of instruction quality because it preserves install intent | `[E12]` | "体系化的重命名" |
| Search/filter habits reduce avoidable work and wrong-target inspection | `[E11]` | "善于使用搜索" |

`[GAP — needs user input]`: source silent on endorsement thresholds, comment-section reliability, changelog minimums, or whether installer screenshots count as sufficient instructions.

## 3. Risk signals (FRAMEWORK)

| Risk | Source | Anchor |
|---|---|---|
| No explanation means risk cannot be assessed | `[E12]` | "没办法评估潜在的风险" |
| No说明 files should be skipped by default | `[E12]` | "没有说明的mod文件，宁愿不装" |
| Installing without reading creates later sorting/debugging debt | `[E12]` | "耐心仔细阅读每一个Mod的说明" |
| Poor local names make patch ownership unrecoverable weeks later | `[E2]` | "过两周之后就会忘记" |
| Bad naming can make disable/uninstall incomplete and harm saves | `[E2]` | "不会漏掉什么东西导致存档崩坏" |
| Scripted mods can be riskier to disable than to leave alone | `[E12]` | "关闭掉一些带有脚本的Mod" |
| Wrong manager/profile/instance can mix state from different games or packs | `[E11]` | "出现mo2混淆的情况" |
| Plugin display order in MO2 is not always the true in-game answer when masters/order are wrong | `[E11]` | "游戏会内部调节加载顺序" |

`[GAP — needs user input]`: source silent on modern installer-specific hazards such as preselected FOMOD defaults, optional ESL conversion, or per-runtime file variants.

## 4. Fit-with-pack signals (FRAMEWORK)

- Installation choices must preserve the upstream INCLUDE verdict from `evaluating-bgs-mods`; this skill does not re-decide whether the mod belongs. `[E12]` "端正的心态"
- The chosen variant/patch should be named by role so pack architecture remains inspectable later. `[E2]` "分类到补丁"
- A compatibility patch belongs either with its main file or in a patch category only if that supports later debugging. `[E2]` "跟着主文件一起分类"
- Downloaded archives should be filed and renamed consistently with the installed mod/category. `[E2]` "压缩包的文件名称"
- Profiles can express different pack/play styles; install decisions must happen in the intended profile. `[E11]` "不同的mod配置方式"
- If author instructions require a tool, use only the needed function rather than turning tool learning into a new project. `[E12]` "某个小功能罢了"

`[GAP — needs user input]`: source silent on a formal pack-variant matrix, default language for recording FOMOD choices, and exact MO2 separator conventions.

## 5. Red flags (thought → reality, FRAMEWORK)

| Thought | Reality | Source |
|---|---|---|
| "The file is here, so I can install it without the page." | Same files without说明 lose the risk surface. | `[E12]` "仅仅只是搬运文件" |
| "The instructions are English; skip to the download button." | Translate and understand; language is not an excuse. | `[E12]` "说明是英文，也请耐着性子" |
| "No instructions probably means simple install." | No说明 is a risk signal, not simplicity. | `[E12]` "下意识地觉得不安" |
| "I'll keep the archive's default vague name." | Vague names destroy patch ownership and debugging. | `[E2]` "这是不能接受的" |
| "The manager UI says category X, so trust it." | Author/curator role matters more than auto-tags. | `[E2]` "并不往往是你想要的标签" |
| "Plugin name and installed mod name are the same." | They may differ; search the right surface. | `[E2]` "插件名字...不相同" |
| "If I don't see it in the game folder, MO2 failed." | MO2-projected tools must launch through MO2. | `[E11]` "通过mo2启动" |
| "Bilibili subtitle is enough for this install flow." | Subtitles here are thin/noisy; prefer richer scripts/page说明. | `[bv3]` "♪ 音乐 ♪" |

## 6. Rationalizations (excuse → reality, FRAMEWORK)

| Excuse | Reality | Source |
|---|---|---|
| "I'll install first and read later." | Reading is the install step that prevents risk blindness. | `[E12]` "装MOD之前多看" |
| "The mod manager will handle it." | Manager automation does not replace author-specific instructions. | `[E12]` "除非Mod作者有特别说明" |
| "I can leave default names; I remember what this is." | Future-you forgets, then debug time explodes. | `[E2]` "会花很多的精力" |
| "A patch can be named just 'patch'." | Patch names must preserve what they patch. | `[E2]` "到底是谁的补丁" |
| "Global MO2 instance is convenient enough." | Mixed instances can point tools at the wrong game/state. | `[E11]` "混淆的情况" |
| "If a tool is recommended, learn the whole tool now." | Install only needs the author-required function. | `[E12]` "某个小功能罢了" |
| "Disable is safe rollback." | Script-heavy disables can worsen the state. | `[E12]` "引发更严重的问题" |
| "Subtitles prove the install detail." | Some subtitle files contain almost no usable instruction content. | `[bv9]` "♪ 音乐 ♪" |

## 7. Game-specific facts → KB (NOT skill content)

### Cross-game
- Author说明 is the primary install-evidence surface; missing说明 is a reject/stop signal. `[E12]` "宁愿不装"
- Original pages are preferred because they preserve install requirements and consequences. `[E12]` "信息量是最充足的"
- Manager UI differs, but instruction interpretation stays portable. `[E2]` "思路是一样的"
- MO2 tools must launch under MO2 to see projected files. `[E11]` "通过mo2启动"
- Profiles and instances are pack-state boundaries, not decoration. `[E11]` "管理的游戏，对应的模组状态"

### Game-specific operational facts
- `[GAP — needs user input]`: source set does not provide game-specific FOMOD option rules, runtime-version variant rules, script-extender-version matrices, or archive/loose precedence facts for this skill. Those belong in KB records queried at runtime, not in `SKILL.md`.

## Orchestrator notes

- The strongest extracted frame is not "follow a checklist"; it is "read the author说明 until install intent, requirements, and consequences are understood." `[E12]` "多主动思考"
- E2/bv12 are Vortex-era; keep principles (traceability, naming, categories), discard click paths. `[E2]` "操作上会有不同"
- bv3 and bv9 are too thin to ground install doctrine beyond a caution about subtitle quality. `[bv3]` "♪ 音乐 ♪"
