# Source-mined extraction: proactive post-install batch testing judgment

Sources mined for this extraction:
- `[bv1]` = `.opencode/artifacts/sixiang-sources/bilibili/01-starfield-papyrus-workflow.txt` (intended Starfield Papyrus workflow subtitle, but captured text is unrelated phone-screen-protector testing content)
- `[SFreview]` = `F:\my clip\Starfield\Review\Starfield个人评价大纲.txt`
- `[SFtech]` = `F:\my clip\Starfield\Review\Starfield引擎与技术力的讨论.txt`
- `[E12]` = `F:\my clip\FO4\MOD Tutorial\E12\Fallout 4 Mod整合搭建教程.txt`
- `[E10]` = `F:\my clip\FO4\MOD Tutorial\E10\1.txt`

[GAP — needs user input]: the available corpus does **not** contain a clean, explicit BB84 "post-install testing protocol". It contains adjacent evidence: patience/process, recent-mod rollback intuition, crash/perf diagnostic examples, Starfield engine/content observations, engine loading/save-state discussion, and one Bilibili file whose text appears mismatched to the intended Starfield Papyrus topic. This extraction keeps the testing skill thin on purpose.

## 1. What "verifying an install batch" means

Framework scope: verify the **batch just added**, not the whole pack and not a deep diagnosis pass.

Source-supported points:
- Testing must be close to the change that introduced risk. `[E12]` says when bugs/CTDs appear, "直接关闭最近装的几个模组" and only then escalate to bisection; this implies the newest batch is the first risk boundary, not an abstract whole-pack sweep. `[E12]`
- Process exists to make later diagnosis possible. `[E12]` says a normalized install workflow includes grouping and systematic renaming of newly installed mods so that future full-list diagnosis is not buried under "各种不同格式，中英混杂，起名随意的几百个mod".
- Stability is only the threshold, not the final quality claim. `[E12]` closes with "一个稳定，没有什么问题的整合包...仅仅只是一款优秀整合包的门槛"; proactive testing proves the floor, not the pack's soul.

[GAP — needs user input]: the corpus does not define exact batch size, number of locations to visit, minutes to idle, combat duration, save/reload cadence, or acceptance thresholds. Those must come from the pack curator and per-game KB records.

[GAP — needs user input]: no source states a universal "test every new mod individually" vs "test every small batch" rule. The skill should ask for / infer the current batch boundary from `curating-bgs-modpack` once that sibling exists.

## 2. Quality signals

Positive evidence is concrete in-game readback that the batch's intended effect exists and no immediate local breakage appears.

| Signal | Source | Anchor |
|---|---|---|
| The changed place/mechanic must be inspected in-game, not only in a manager UI | `[E12]` | "游戏里具体某个数据是否存在Mod冲突...是在管理器界面看不出来的...要用xEdit加载所有的模组列表" |
| For a performance/scene-fix-style change, meaningful proof is before/after behavior at the affected place | `[E10]` | "进入游戏可以看到原本掉帧的芳邻镇门口...帧数提高了，并且Draw Call也恢复到了正常值范围" |
| A mod-impact test should go to the specific place where the impact is expected | `[E10]` | "来到游戏中出现掉帧/场景消失的位置" |
| Content-facing checks should look for the promised local content/experience, not a generic route | `[SFreview]` | exploration value comes from "看看那里有什么我不知道的东西" and unique, non-repeated encounters |
| Engine/performance claims need measured context, not vibes | `[SFtech]` | "星空经过我的测试...四核八线程的CPU会跑得特别满" |
| Loading transitions can be legitimate reset/self-check points for script/world state | `[SFtech]` | "加载机制可以让游戏在更换场景的时候清理存档内的脚本，检测脚本的异常状态，以及重置状态" |

Candidate skill phrasing supported by these signals:
- visible new content/mechanic appears where the batch said it would;
- expected local mechanics can be exercised once in the target context;
- immediate CTD / obvious scene absence / severe local FPS collapse does not occur in the touched place;
- no acceptance claim from menu load alone.

[GAP — needs user input]: "no error overlays" is required by the task brief, but the sources do not enumerate universal overlay strings, missing-mesh markers, log banners, Papyrus error indicators, or Starfield/Skyrim/Fallout-specific HUD warnings. Put concrete overlay/error facts in KB.

[GAP — needs user input]: no source provides mod-category-specific positive tests (quest mod, NPC replacer, weapon, settlement, weather, UI, animation, perk overhaul, script framework). The skill must require the curator to name the intended impact, then query KB for category-specific routes.

## 3. Risk signals (in testing posture)

| Risk | Source | Anchor |
|---|---|---|
| Silent breakage: manager load is not enough; wrong/overridden data may only appear in xEdit/in-game readback | `[E12]` | "管理器界面看不出来...要用xEdit加载所有的模组列表" |
| Over-trusting a boot/menu success hides local failures | `[E12]` + `[E10]` | Stability is only a threshold; E10 verifies at the affected place, not at the menu |
| Save baking before test can make rollback harder, especially with scripts | `[E12]` | "关闭掉一些带有脚本的Mod反而会引发更严重的问题" |
| Treating deep crash/perf diagnosis as normal testing expands the scope | `[E12]` | crash/perf tools and log reading belong to 排查错误, not the initial install-flow pass |
| Assuming all loading screens are bad misunderstands engine hygiene | `[SFtech]` | loading can clean scripts, detect abnormal state, and reset state |
| Overconfidence replaces patience after a few successful installs | `[E12]` | "学会耐心，能帮助我规避70%可能出现的问题" |

[GAP — needs user input]: the corpus does not name save-safe test-save mechanics, save-cleaning tools, or per-game persistence hazards. The skill should say "do not commit the main progression save until the batch passes" but defer exact save protocol to KB/user input.

[GAP — needs user input]: the corpus does not prove "mod loaded but visibly absent = load order wrong" as a universal rule. It is a plausible testing signal, but the cause may be missing asset, condition gating, script init delay, bad installation option, or load order. Phrase as "silent absence is a failure signal; escalate to diagnosis", not as a fixed cause.

## 4. Test scope discipline

Framework:
- **Batch-bounded**: test the mods just added and the impact zones they claim to touch. If failure appears, hand off to diagnosis instead of expanding the proactive pass into a full investigation.
- **Impact-aware**: tests follow the mod's promised impact. A weather batch needs weather/worldspace checks; a script/mechanic batch needs a minimal mechanic trigger; a texture-only batch needs visual presence and missing-asset scan. `[GAP — needs user input]`: source does not enumerate these categories.
- **Save-hygienic**: use a disposable / pre-batch save boundary; do not save over the main progression before the batch is accepted. Support: script mods can become harder to disable `[E12]`; loading cleans/reset script state `[SFtech]`, so save/load state is part of the semantics.
- **Before next batch**: stop and record PASS / FAIL / NEEDS MORE INFO before installing the next batch. Support: `[E12]` frames recent mods as first suspect and recommends patience/process.

[GAP — needs user input]: no source provides a universal "clean save" definition across games. Do not invent one.

[GAP — needs user input]: no source provides a universal smoke-route length. Per-game route lists belong in KB.

[GAP — needs user input]: no source provides acceptance thresholds for FPS, script latency, spawn count, quest startup delay, or cell traversal count.

## 5. Red flags

| Thought | Reality | Source |
|---|---|---|
| "The main menu loaded; the batch is fine." | Menu load is not impact verification; source examples verify in the affected game location. | `[E10]` |
| "MO2 shows it enabled, so the in-game data is correct." | Some data conflicts are invisible in the manager; xEdit/in-game readback is required for actual state. | `[E12]` |
| "I'll save over my main character now and test later." | Script-bearing mods can become harder to disable; save state is not free. | `[E12]` |
| "If something fails, keep testing everything until I understand it." | Proactive testing stops at failure and hands off to diagnosis; deep crash/perf tracing is a different workflow. | `[E12]` |
| "A loading screen means the engine is weak; avoid save/load checks." | Loading can clean scripts, detect abnormal state, and reset state. | `[SFtech]` |
| "I know enough now; no need for a careful batch check." | Patience is the cited way to avoid most avoidable problems. | `[E12]` |

[GAP — needs user input]: no source directly mentions red error overlays, missing texture colors, missing mesh markers, or Starfield/Skyrim/FO4 console teleport commands. Keep those out of the framework and route to KB.

## 6. Rationalizations

| Excuse | Reality | Source |
|---|---|---|
| "Testing the whole pack every time is more thorough." | The actionable boundary is the batch just added; whole-pack diagnosis belongs after a failure signal. | `[E12]` |
| "If the mod is enabled, absence in-game probably just means I looked in the wrong place." | Maybe, but absence is still a failed verification signal; prove the intended impact or escalate. | `[E12]` + `[GAP]` |
| "I'll make a real save so the mod initializes properly." | Use save boundaries deliberately; do not bake unverified scripts into the main progression. | `[E12]` / `[SFtech]` |
| "No CTD in five minutes means accepted." | No CTD is one signal; acceptance is visible intended effect + no immediate local breakage at the target context. | `[E10]` |
| "Console commands are the same across BGS games; I can just write them here." | The architecture requires per-game facts in KB; the skill stays game-agnostic. | architecture spec |
| "The source is thin, so fill with common-sense QA." | BB84 anti-checklist voice forbids invented filler. Mark `[GAP]` and ask / query KB. | task constraint |

[GAP — needs user input]: no source provides a rationalization table for proactive testing specifically. The rows above are derived from adjacent crash/perf/process evidence and task constraints, not from a dedicated testing lecture.

## 7. Game-specific facts to KB

These are **not** skill-body content. They are candidates/deferred needs for per-game KB backfill.

### Fallout 4
- Performance/scene route example: go to the affected FPS / scene-missing location, rotate view to lowest FPS, inspect ENB Profiler Draw Call count, use console `tpc` as a visual-culling diagnostic, compare normal vs abnormal region. `[E10]` anchors: "来到游戏中出现掉帧/场景消失的位置", "控制台输入tpc", "Draw Call和帧数".
- Better Console is used to identify current data in-game for FO4-style non-CTD issues. `[E10]` / `[E12]`.
- Buffout4 provides crash logs; scanner can translate logs into human language, but attribution can be unreliable (already captured in evaluating extraction). `[E12]`.
- [GAP — needs user input]: requested FO4 console-command catalog (`coc`, `tcl`, `tgm`, safe test cells/routes) is **not present** in the mined testing sources. Defer to KB backfill.

### Skyrim
- More Information Console is named as the Skyrim analogue for in-game data identification. `[E12]`.
- `.NET Script Framework` is named for crash logs, and `[E12]` explicitly says there is no FO4-style scanner in that source context; ask old hands / read logs manually. `[E12]`.
- [GAP — needs user input]: Skyrim console commands, safe cells, and route catalogs are not in the mined sources. Defer to KB backfill.

### Starfield
- Engine/performance context: Starfield can benefit from CPU/GPU improvements differently than FO4; source gives measured CPU-thread examples, not a modpack test route. `[SFtech]`.
- Content/exploration context: the review criticizes repeated points of interest and values unique, non-repeated discovery ("看看那里有什么我不知道的东西", "独特，不重复的东西"). This is a content-quality clue, **not** a concrete post-install route. `[SFreview]`.
- Loading can clean scripts, detect abnormal states, and reset state. `[SFtech]`.
- RenderDoc hook caused crash in the cited experiment; treat heavyweight graphical instrumentation as non-routine. `[SFtech]`.
- [GAP — needs user input]: the intended `[bv1]` Starfield Papyrus workflow subtitle appears to be unrelated phone-protector content (anchors include "钢化膜", "水滴角测试", "透光测试"). It contributes no reliable Papyrus/modpack verification procedure.
- [GAP — needs user input]: Starfield console commands and test routes are absent from the mined sources. Defer to KB backfill.

### Cross-game
- Per-game console commands and verification routes are facts, not framework. The skill must query KB, and if KB is silent, report `[GAP]` instead of inventing a route.
- [GAP — needs user input]: no cross-game universal safe-save / disposable-save procedure was found.
