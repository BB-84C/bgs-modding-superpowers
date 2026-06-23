# Source-mined extraction: BB84's diagnostic ladder judgment

Sources:
- `[E4]` = `F:\my clip\FO4\MOD Tutorial\E4\New Text Document.txt` (GB18030; FO4 performance/crash/freeze optimization episode)
- `[E10]` = `F:\my clip\FO4\MOD Tutorial\E10\1.txt` (GB18030; mod-induced FPS diagnosis / precombine-previs episode)
- `[bv4]` = `.opencode/artifacts/sixiang-sources/bilibili/04-fo4-cpu-render-fps.txt` (AI subtitle; title says CPU/render principles, transcript body appears unrelated)
- `[bv10]` = `.opencode/artifacts/sixiang-sources/bilibili/10-fo4-optimization-fps.txt` (AI subtitle; transcript body appears unrelated drama short, not the modding video)
- Prior cross-check: `.opencode/artifacts/sixiang-build/evaluating-bgs-mods/framework-extraction.md` already captured BB84's auto crash-log-scanner mis-attribution warning from `[E12]`. This extraction keeps that as a diagnosed risk signal but marks the supplied E4/E10/bv4/bv10 slice silent where applicable.

## 1. What "diagnosing" means

Diagnostic work is a ladder: symptom -> reproducible signal -> isolated trigger -> root cause. It is not "scanner says X, yank X" and it is not "install the optimization list until the symptom disappears."

- Start from the actual symptom class: crash / freeze / stutter / low FPS / missing scene / flicker. `[E4]` frames the episode as solving "卡顿，闪退，低帧数" and asks the viewer to "请耐心看完" before operating.
- A diagnosis earns confidence only when the symptom is reproduced in a known place/action. `[E10]` moves the user to "游戏中出现掉帧/场景消失的位置", then asks them to rotate view until FPS is lowest before measuring.
- For FPS/performance, the meaningful evidence is the engine bottleneck signal, not generic graphics settings. `[E10]` anchors diagnosis on Draw Call: "Draw Call 过高，说明CPU要处理的渲染指令就越多" and "CPU所有的渲染指令堵死在一条线" while the GPU waits.
- For crash/freeze, the meaningful evidence is a crash log or a repeatable trigger. `[E4]` describes Buffout-style logs as letting the user "定位到引起问题的贴图文件或者mod" and "节省排错的时间"; the scanner/attribution layer remains heuristic, not verdict.
- For engine-vs-mod attribution, prove whether the engine optimization data stopped working before prescribing a mod or patch. `[E10]` uses `tpc` as an experimental control: if disabling culling does not change Draw Call/FPS, the local culling data was already failing.
- `[GAP]` The supplied source slice does not define a complete cross-game crash-log taxonomy. Per-game crash logger names and signatures belong in KB, not this framework.

## 2. Quality of signals

| Signal | Why it is strong | Source / anchor |
|---|---|---|
| Reproducible location/action | Turns "my game is slow" into a testable state | `[E10]` "来到游戏中出现掉帧/场景消失的位置"; "旋转视角，让帧数到达最低" |
| Measured bottleneck, not vibes | Separates CPU/render bottleneck from generic GPU-quality tuning | `[E10]` "Draw Call 过高"; FO4/Skyrim "只支持单核单线程CPU运行游戏" |
| Control experiment | Checks whether the suspected engine feature is already broken | `[E10]` `tpc`: if Draw Call/FPS do not change, "说明是视觉剔除失效了" |
| Crash log presence | Gives concrete stack/file/module evidence, but still needs interpretation | `[E4]` crash logs "迅速定位到引起问题的贴图文件或者mod" |
| Isolated trigger | Narrows root cause to a cell, asset, action, or recent change | `[E10]` records current cell FormID with a console inspector, then locates it in edit tooling |
| Engine-vs-mod attribution | Prevents blaming a mod when the engine limit/data path is the actual bottleneck | `[E10]` scene edits + bad sort can break precomputed data; `[E4]` optimization mods help only if the matching bottleneck exists |

Weak signals:
- "It booted once" — not a pass for a symptom that needs repeatability.
- "A scanner named one mod" — an input, not attribution.
- "It started after the last mod" — a lead, not proof.
- "Lower graphics did not help, so the game is cursed" — `[E10]` explains CPU/render-command bottlenecks where GPU quality tradeoffs do not solve the actual line.
- `[GAP]` `[bv4]` and `[bv10]` do not provide usable diagnostic content beyond title metadata in the captured subtitle files.

## 3. Risk signals in the diagnosis itself

| Risk | Why it breaks diagnosis | Source / anchor |
|---|---|---|
| Scanner over-confidence | Auto-attribution can mis-name the responsible mod or file; treat as a lead only | Prior `[E12]` extraction: "日志扫描器经常会把闪退原因归咎到不相关的模组上面". `[GAP]` supplied E4/E10 sources discuss crash logs, not scanner fallibility. |
| Blame-the-last-mod-installed bias | Recent change is useful context, but load order and engine data can make an older mod become the visible failure | `[E10]` scene/cell data can be overwritten by ordering; even unrelated placed objects can override optimization data if loaded after a repair layer. |
| Symptom-without-evidence prescription | Installing/removing optimization mods without proving the bottleneck can mask or move the problem | `[E4]` many recommendations are conditional: "如果本身没这个问题则不需要装"; `[E10]` says the fix requires understanding what the copied records mean. |
| Boot-success false green | Startup proves only that the loader passed once; it does not prove the original CTD/FPS route is fixed | `[E10]` validates by returning to the exact low-FPS/missing-scene location and checking FPS/Draw Call/scene visibility. |
| Generic "lower settings" bias | In these engines, CPU/render-call bottlenecks can survive ordinary quality reductions | `[E10]` GPU waits while CPU sends render commands; `[E4]` warns high FOV/shadows/particles matter, but the core precombine/previs issue is separate. |

## 4. Diagnostic posture

BB84's strongest diagnostic instruction is not a tool command; it is patience and meaning. The source repeatedly frames the work as high-information, high-patience, and not reducible to button pressing.

- Patience is an operating discipline, not a personality trait. `[E4]` "如果你真的很想解决...请耐心看完，有条件的话，也许可以做点笔记".
- The hard part is understanding why the operation means what it means. `[E10]` rejects "单纯按几个按钮就能搞定" and says the operations "全部都需要你理解它们的意义".
- FPS diagnosis is engine diagnosis. `[E10]` explains precomputed scene data, culling databases, Draw Call, CPU single-thread pressure, and GPU idling before any prescription.
- FO4/Skyrim-style Creation Engine performance is often CPU/render-command-bound. `[E10]` explicitly says FO4 and Skyrim are old games that "只支持单核单线程CPU运行游戏"; therefore the normal "trade visual quality for frames" instinct is incomplete.
- Per-game tool names are not the framework. The framework asks for current game logs, reproducible triggers, engine signals, and isolated readback; the KB supplies which logger/console/editor is current for the target game.

## 5. Red flags

| Thought | Reality | Source |
|---|---|---|
| "The scanner blamed X, so remove X." | Scanner attribution is a heuristic; prove with a reproduced trigger and readback before yanking. | Prior `[E12]`; `[GAP]` in supplied E4/E10/bv4/bv10 slice. |
| "If it boots, the crash is fixed." | Boot is not the original route. Re-run the exact crash/freeze/load route or the same low-FPS location. | `[E10]` validates at the original location with FPS/Draw Call/scene visibility. |
| "FPS is low, lower texture quality first." | CPU Draw Call/culling failure can be the bottleneck while GPU waits. | `[E10]` "显卡只能...等CPU". |
| "The last mod caused it." | The last mod is context, not root cause; ordering and inherited cell data can expose an older problem. | `[E10]` placed object data after a repair layer can override optimization data. |
| "Just install the famous optimizer." | Some fixes are conditional; if the symptom is not present, the tool/mod is not automatically needed. | `[E4]` "如果本身没这个问题则不需要装". |
| "I don't need to understand the patch, just copy the steps." | Diagnosis requires knowing what each copied record/data layer means. | `[E10]` "全部都需要你理解它们的意义". |

## 6. Rationalizations

| Excuse | Reality | Source |
|---|---|---|
| "I need a quick fix; I will try optimization mods until one sticks." | Quick-fix loops hide the signal. Diagnose the symptom route and bottleneck first. | `[E4]` patience/note-taking framing; `[E10]` measurement-first route. |
| "Crash logs already tell me the answer." | Logs are evidence, not self-interpreting; scanner output is weaker still. | `[E4]` logs locate leads; prior `[E12]` warns scanner mis-attribution. |
| "Draw Call is too technical; I will just lower settings." | The engine can be CPU-command-bound; if you ignore Draw Call, you may tune the wrong subsystem. | `[E10]` Draw Call/CPU/GPU waiting explanation. |
| "The problem disappeared once, so done." | A fix needs repeatable absence on the original trigger, not one clean launch. | `[E10]` before/after validation at exact location. |
| "This tool worked for FO4, so it is the general BGS answer." | Skill framework is cross-game; game-specific loggers and console tools live in KB and must be queried per game. | Architecture spec game-agnostic rule; `[GAP]` supplied sources are FO4-heavy. |
| "I can skip the explanation and follow the recipe." | The BB84 posture is anti-checklist: understand what the operation means, or the next variant will break you. | `[E10]` rejects button-only copying. |

## 7. Game-specific facts to KB

### Fallout 4

- Existing FO4 Buffout records are present under `knowledge/bgs-kb/packs/bgs-kb-fallout4/records/fo4-buffout/` (`buffout4-is-f4se-crash-logger-stack`, `crash-log-first-pass-triage`, `enb-and-buffout-are-different-native-layers`, `runtime-branch-before-crash-log`). Do not duplicate these in the skill body.
- FO4 precombine/previs, Draw Call, culling-control commands, Better Console-style cell inspection, and PRP-style repair details are game facts and should remain in FO4 KB records, not the cross-game skill body. `[E4]`/`[E10]` supply rich FO4 anchors.
- New cross-game KB record needed and authored in this batch: `debugging.scanner-attribution-skepticism.v1` for the scanner-attribution warning.

### Skyrim

- Requested fact bucket: `.NET Script Framework` crash logs plus no-auto-scanner posture. `[GAP]` The supplied E4/E10/bv4/bv10 source slice does not ground Skyrim tool specifics. Add or update per-game KB only after source grounding.

### Starfield

- Requested fact bucket: no Buffout-equivalent in the 2023-08 corpus / current diagnostic tool gap. `[GAP]` The supplied E4/E10/bv4/bv10 source slice does not ground Starfield diagnostic tooling. Record as a cross-game KB gap, not a skill-body fact.

### Cross-game

- Framework fact: symptom-first, evidence-first, scanner-skeptical diagnosis is cross-game.
- Per-game fact: which logger, console tool, crash signature, engine command, or editor route proves the symptom belongs in KB.
