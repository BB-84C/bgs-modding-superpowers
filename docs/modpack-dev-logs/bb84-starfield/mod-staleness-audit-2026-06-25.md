# Nexus 全量 Staleness 审计 — BB84 Starfield (BB84自用2 profile)

**生成时间**: 06/25/2026 12:50:48
**审计范围**: 125 个 Nexus mod (modid 去重后 125 unique；inventory 中部分 mod 在 modulo 重复)
**深度调查**: 14 个 mod 走了完整 fate investigation 流程 (per KB record `install-planning.audit-grade-mod-fate-investigation.v1`)
**游戏版本**: Starfield 1.16.244
**Raw data**: `.opencode/artifacts/bb84-starfield-audit-2026-06-25/merged-audit-results.json` (~146 KB)

---

## TL;DR — Tier 分布

| Tier | Count | 含义 | 优先级 |
|---|---:|---|---|
| **CONTINUITY-REPUBLISHED** | 2 | 原作者改了 modid 重发，建议迁移到新 listing | 高 |
| **DEAD-LISTING-AT-RISK** | 4 | listing 死了 + 有 systemic 组件（esm/papyrus/dll），将来 patch 可能炸 | 高（监控）|
| **GENUINE-UPDATE-AVAILABLE** | 1 | 真有版本更新可用 | 中 |
| **DEAD-LISTING-FUNCTIONAL** | 1 | listing 死但本地 essence 是 pure-asset，留着没事 | 低（记账）|
| **YELLOW-RECLASSIFIED** | 3 | 原 Red 被 version-comparator 误伤；归一化后是 Yellow，待 spot-check | 中 |
| **YELLOW** | 13 | 真 version-aged 或久未更新但 published | 中低 |
| **HEALTHY-FALSE-POSITIVE** | 6 | 原分类器误判，深度调查证实健康 | — |
| **HEALTHY** | 95 | 版本归一化后实际健康 | — |

**总判断**：modset 健康基线良好（95 + 6 = 101 / 125 = 81% healthy）。需要 curator 真正决策的 mod 只有 4-10 个；其余 100+ 是 noise + 误报。

---

## 1. 需要决策的 mod (Action Required)

### 1.1 CONTINUITY-REPUBLISHED — 原作者改 modid 重发，建议迁移

####  ([Nexus #9710](https://www.nexusmods.com/starfield/mods/9710))
- **MO2 folder**: `Denser Vegetation - GRiNDTerra`
- **API status**: `removed`
- **Author**: ItsmePaulieB ([profile](https://www.nexusmods.com/starfield/users/128309393))
- **Essence**: plugin-only (2 files, 3.193 MB)
- **Republish 候选**: Vanilla Biomes Enhanced- A GRiNDTerra Mod ([Nexus #16176](https://www.nexusmods.com/starfield/mods/16176))
  - 证据: Same author profile lists this active 2026 environment mod; its visible card says it provides random tree and shrub sizing, denser forests, sandier deserts, less/easier rocks, and a new fauna placement system, directly overlapping and broadening the removed Denser Vegetation role.
- **Verdict 依据**: API cache reports the old Denser Vegetation listing as removed, but the same author has an active GRiNDTerra environment-line successor in Vanilla Biomes Enhanced plus a current GRiNDTerra homepage. The installed old artifact is plugin-only ESM, so keeping it as a dead listing is less attractive than migrating to the maintained successor if the pack still wants that biome-density role.
- **建议操作**: migrate
- **理由**: Evaluate and migrate to Vanilla Biomes Enhanced/GRiNDTerra current environment stack rather than treating the removed mod as dead. Keep the old folder disabled only as rollback evidence until the replacement is triaged.

####  ([Nexus #11334](https://www.nexusmods.com/starfield/mods/11334))
- **MO2 folder**: `Just Random Vegetation Rock and Exotic Sizes - GRiNDTerra`
- **API status**: `removed`
- **Author**: ItsmePaulieB ([profile](https://www.nexusmods.com/starfield/users/128309393))
- **Essence**: plugin-only (2 files, 0.902 MB)
- **Republish 候选**:  ([Nexus #](https://www.nexusmods.com/starfield/mods/))
  - 证据: 
- **Verdict 依据**: API cache and Nexus page show the old modid 11334 was removed by author, but the same author is active (profile last active 25 Jun 2026) and maintains a published GRiNDTerra homepage (12307) plus current published modules that split the removed combined concept into maintained pieces: Random Creature and Robot Sizes (9920), Rocks mini mod (13094), Fauna mini mod (14803), and Fantastical Frontiers (16215). Installed old artifact is a single ESM (Grindrandoveg.esm), so keeping the dead listing is plugin-riskier than reconciling to the maintained lineage.
- **建议操作**: Do not search unrelated replacements first; reconcile this as a same-author GRiNDTerra successor split. Evaluate replacing the old combined ESM with the current GRiNDTerra modules that match the pack's ecology/biome intent, then retire the old mod under [弃用] only after comparison.
- **理由**: Continuity is not exhausted: same author, same mod family, maintained 2026 modules, and an explicit GRiNDTerra homepage. Because the old artifact is plugin-only, the safer curator path is lineage migration rather than treating the removed modid as either harmless or dead.

### 1.2 DEAD-LISTING-AT-RISK — listing 死 + systemic 组件，监控

####  ([Nexus #2830](https://www.nexusmods.com/starfield/mods/2830))
- **MO2 folder**: `Weapon Swap Stuttering Fix - AddLib 5`
- **API status**: `hidden`
- **Author**: Antonix35 ([profile](https://www.nexusmods.com/starfield/users/1133204))
- **Essence**: **dll-plugin** — 2 files / 0.556 MB | ext: .dll=1, .ini=1
- **Verdict 依据**: API cache says status=hidden available=false; Nexus page readback says hidden by Antonix35 on 16 Dec 2025 with reason: 'This mod is currently not supported by the author(s) and/or has issue(s) they are unable to fix yet.' Same-author user-mod endpoint returned 404, profile page exposed only metadata (Premium, Verified Mod Author, last active 25 Jun 2026) and no mod list, and web-search attempts found no successor/off-Nexus continuation. Installed essence is a native SFSE DLL plugin using CommonLibSF/Address Library, so it is runtime-sensitive.
- **建议操作**: Keep it in the existing 等待作者更新 separator and disabled; do not spend replacement-search effort unless the pack currently needs this fix active or the author remains hidden through the next SFSE/Address Library update cycle.
- **理由**: The author explicitly hid it because it is unsupported/has unresolved issues, which is stronger than a generic hidden signal. Since this is an SFSE DLL plugin, enabling it on an unsupported Starfield/SFSE runtime is higher risk than living without the fix temporarily.

####  ([Nexus #7569](https://www.nexusmods.com/starfield/mods/7569))
- **MO2 folder**: `Space Ship Landing Reloaded`
- **API status**: `removed`
- **Author**: 7StarC ([profile](https://www.nexusmods.com/starfield/users/7454615))
- **Essence**: **plugin-only** — 3 files / 0.02 MB | ext: .ini=1, .ba2=1, .esm=1
- **Verdict 依据**: API cache reports status=removed and available=false. Same-author profile shows currently published Starfield ship/gameplay mods but no same-name or clear successor to Space Ship Landing Reloaded; installed essence is an ESM plus BA2, so it is not pure asset-only.
- **建议操作**: monitor
- **理由**: Keep the local copy only if it still behaves in-game, but mark it as delisted/systemic and watch for landing/ship-scene regressions after Starfield updates. Do not migrate until a same-author successor or active replacement is identified.

####  ([Nexus #12083](https://www.nexusmods.com/starfield/mods/12083))
- **MO2 folder**: `VaruunTI Habs`
- **API status**: `removed`
- **Author**: GreenRecon ([profile](https://www.nexusmods.com/starfield/users/188657943))
- **Essence**: **mixed** — 3 files / 15.96 MB | ext: .ba2=1, .esm=1, .ini=1
- **Verdict 依据**: API cache says status=removed available=false, version 4.7.6, author GreenRecon/member_id 188657943; Nexus page readback shows 'Removed by author'. Same-author Nexus user-mod endpoint returned 404, profile page exposed only metadata (Verified author, last active 25 Jun 2026) and no per-mod list, and multiple web-search attempts found no successor/off-Nexus continuation. Installed folder is an ESM plus BA2 asset archive, not pure loose assets, so the local artifact may still function but has plugin/content-system risk without upstream continuity.
- **建议操作**: Keep the local copy for now if the pack currently depends on it, but leave it marked as author-removed/at-risk and start a replacement watch for Va'ruun ship-hab alternatives rather than panic-removing it.
- **理由**: No continuity path was found, but there is also no evidence the installed ESM+BA2 is already broken. Because ship-hab content is plugin/asset mixed rather than pure asset, future Starfield ship-system/runtime changes could strand it.

####  ([Nexus #14019](https://www.nexusmods.com/starfield/mods/14019))
- **MO2 folder**: `OwlTech_Pathfinder`
- **API status**: `hidden`
- **Author**: sgtowl ([profile](https://www.nexusmods.com/starfield/users/43919117))
- **Essence**: **plugin-only** — 4 files / 227.616 MB | ext: .ini=1, .ba2=2, .esm=1
- **Verdict 依据**: API cache reports status=hidden and available=false. Same-author Nexus profile shows an active OwlTech ship/hab series but no visible Pathfinder successor; installed essence is ESM plus two BA2 archives, not a pure asset-only folder.
- **建议操作**: monitor
- **理由**: Keep only if the local ship content still loads cleanly, but track it as hidden/systemic and watch for same-author reappearance or an explicit Pathfinder successor. Because no direct successor was found, do not rewrite metadata to another OwlTech modid.

### 1.3 GENUINE-UPDATE-AVAILABLE — 真有更新可用

#### Stroud Premium Edition ([Nexus #12330](https://www.nexusmods.com/starfield/mods/12330))
- **MO2 folder**: `Stroud Premium Edition`
- **版本**: 安装 `2.3.3.0` → 最新 `2.5.3`
- **Author**: Vince134 ([profile](https://www.nexusmods.com/starfield/users/190716729))
- **Essence**: plugin-only (2 files, 13.074 MB)
- **建议操作**: UPDATE to 2.5.3.0. Disable installed 2.3.3.0 mod, move under '[弃用]' separator per the BB84 mod-removal protocol, then install fresh 2.5.3.0 archive from Nexus. CRITICAL pre-update step from author: 'LEAVE NEW ATLANTIS BEFORE INSTALLING/UPDATING' - any active save must travel away from Jemison before swapping the .esm. Re-enable 2.5.3 after upgrade. Re-check translation mod under '[弃用]' if BB84 has a separate zh-CN translation mod for SPE since 2.4.0+ now ships native zh-CN.
- **理由**: Active flagship mod, recent author activity, real available update with curator-relevant new content (native zh-CN translation, docker modules, compat patches). 4 minor versions behind is enough drift that future compat-patches (e.g. SPE x Useful Brigs V6) will assume 2.5.3 baseline. The update-available signal is correct and actionable; the desc-match flag was noise from a deprecated sub-patch description.

---

## 2. 不需要操作但值得记账的 mod (Surfaced for Awareness)

### 2.1 DEAD-LISTING-FUNCTIONAL — listing 死但本地 artifact 没事

####  ([Nexus #6004](https://www.nexusmods.com/starfield/mods/6004))
- **MO2 folder**: `ImmersiveDataSlates`
- **API status**: ``
- **Author**: 
- **Essence**: **pure-asset** — 7 files / 0.05 MB | ext: .nif=5, .ini=1, .txt=1
- **Verdict 依据**: Nexus mod-info endpoint returns status='hidden' / available=false for modid 6004 (author 'jhardingame', member_id 991046, last updated 2023-10-26). Files endpoint 403. Walked MO2 folder D:/Starfield MO2/mods/ImmersiveDataSlates: 5 loose .nif mesh files under meshes/animobjects, meshes/items/dataslate, meshes/setdressing/ucintdossier — NO .esp / .esm / .esl / .pex / .dll / .ba2. Mod is pure loose-file mesh replacement that wins over base-game .nif paths via [Archive] bInvalidateOlderFiles=1 (per author's own install note in nexusDescription). Same-author republish check inconclusive: Nexus public API has no /users/{id}/mods.json endpoint (returns 404 by design); next.nexusmods.com profile pages return 403 Cloudflare bot challenge; html.duckduckgo.com search 302→bot challenge. GitHub api.github.com/search/users for 'jhardingame' returns 0 hits and search/repositories for 'ImmersiveDataSlates starfield' returns 0 hits — strong negative for any open-source republish. NOTE: user described the essence as 'just a texture replacement, completely fine to keep'. Filesystem evidence refines this: it is mesh replacement (.nif), not texture (.dds), but the FUNCTIONAL class user meant — pure-asset loose-file override with zero script/plugin/DLL surface — is exactly what is on disk. User's keep-it-safely intuition is validated.
- **建议操作**: Keep enabled. Pure-asset mesh replacement with no scripts, plugins, masters, or DLL — nothing breaks if the Nexus listing stays hidden. Move into a curator-managed '[隐藏/已撤页]' separator with a comments= note in meta.ini documenting that the listing is hidden but the mod is functionally complete. Take no rehosting action (no upstream to track and no replacement candidate found). If a future engine update changes the .nif format and breaks data-slate rendering, that is the trigger to look for a replacement; until then there is nothing actionable. — DEAD-LISTING-FUNCTIONAL outcome is precisely the case where a binary 'Red — replace' verdict is wrong. The mod's correctness does not depend on the Nexus listing being alive: it ships ~50 KB of static mesh assets that the game engine resolves through loose-file precedence. No SFSE bindings, no scripted hooks, no master dependencies, no per-game-version compiled code — therefore no future-Starfield-patch class of risk beyond raw .nif schema (which is extremely stable across BGS engine generations). Continuity-republish search was best-effort negative (API endpoint absent, web search bot-blocked, GitHub clean) but the FUNCTIONAL-FINE evidence is the load-bearing signal, not the continuity signal.

### 2.2 HEALTHY-FALSE-POSITIVE — 原分类器误判，深度调查证实健康

这些 mod 触发了原 Red/Yellow 分类器但是误报。每个都附**误报原因**，可用于改进未来的 audit classifier。

| Mod | Modid | 误报原因 | 实际状态 |
|---|---:|---|---|
| [The Eyes of Beauty - Starfield Edition](https://www.nexusmods.com/starfield/mods/493) | 493 | Nexus API: status='published', available=true, mod_id=493, mod-page version='1.1.1', updated_time=2023-10-13 (32 months ago — true, but stable not stale), 306,677 downloads / 8,028 endorsements, author LogRaam member_id=308756 (well-known across the BGS-Edition Eyes of Beauty franchise: Skyrim, Fallout, Starfield). meta.ini nexusFileStatus=3 ('update available' file-level signal). HOWEVER the file BB84 installed is file_id=780 = 'TEOB Starfield - pack 1 - Replacer' (category OPTIONAL, file-version 1.0.0, uploaded 2023-09-03) which is the MANUAL drop-in texture package, NOT the MAIN page item. The MAIN page item is file_id=16756 = 'The Eyes of Beauty - Replacer Installer tool' (category MAIN, file-version 1.1.1) — an INTERACTIVE .exe installer tool that does NOT play nicely with MO2's VFS. BB84 correctly chose the manual variant for MO2 workflow; the '1.1.1' would require running an .exe outside MO2 to populate Pack-1+Pack-2+Specials into a Stock-Game-like folder. So the '1.0.0.0 → 1.1.1' delta is NOT a same-product update — it is a CROSS-PRODUCT-VARIANT version mismatch. The OPTIONAL Replacer file at 1.0.0 IS the current and only version of THAT variant (no newer file_id supersedes it in files[]). Essence walk: 13 .dds eye-iris textures under Textures/actors/human/faces/eyes/* (224 MB of compressed-DDS), zero scripts/plugins/DLL — pure-asset texture replacer. Description desc-match heuristic likely flagged on age-related phrasing or 'older textures' references, not lifecycle concerns. | Keep enabled. NO update action — what looks like a '1.0.0.0 → 1.1.1' update path is actually a switch from the (MO2-friendly) manual replacer variant to the (MO2-hostile) interactive .exe installer variant. Stay on the manual variant. OPTIONAL enhancement: BB84 can download Pack 2, Pack 3, Pack 4 optional .rar files directly and add as separate MO2 mods (or layer into this folder) for more iris-variant coverage — but those are content additions, not version updates, and depend on aesthetic preference. Annotate meta.ini comments= to clarify: '[manual-variant] 选用 Replacer-only 路径，正版 1.0.0 是该 variant 的 current，page-version 1.1.1 是另一个 installer-tool variant，与 MO2 工作流不兼容，不应升级。' Update curator's '32mo old → Yellow' classifier to gate on whether the mod is still published AND whether the installed file variant has a newer file_id in the same variant lineage. |
| [Finally Accurate Npc Aiming](https://www.nexusmods.com/starfield/mods/7050) | 7050 | API status=published, available=true, fetched today. Mod is a 73KB ESM that nukes Object-Modification fire-spread records on Quality Tier 1 weapons - pure data edit, no scripts, no .dll. The installed version string 'd2025.8.7.0' is BB84's curator-internal versioning convention (d-prefix = date stamp, 2025.8.7 = build date 2025-08-07), NOT a Nexus version. meta.ini comments field literally documents this: '[UPDATE：1.0.0.0]' is BB84's note that the Nexus baseline is 1.0.0.0. BB84 keeps the local d-version tag to record that they have inspected / locally-rebuilt / xEdit-patched the ESM on that date. | KEEP installed. No action required. Feed the audit classifier a version-format escape: when installed version matches /^d\\d{4}\\.\\d{1,2}\\.\\d{1,2}\\.\\d+$/, treat as BB84-local build-date stamp and skip the version-drift signal (use the file_id / file hash instead). Do NOT downgrade BB84's locally-tagged d-version back to '1.0.0.0' from Nexus - that would erase BB84's record of having inspected/built the file locally. |
| [Starfield Engine Fixes - SFSE](https://www.nexusmods.com/starfield/mods/10457) | 10457 | Nexus API: status='published', available=true, version='20.2', updated_time=2026-06-21T09:32:19-04 (4 days fresh at audit time), 574,700 downloads / 4,063 endorsements / 184,139 unique downloaders, author LarannKiar member_group_id=27 (premium/notable contributor). The mod ships multiple parallel game-version branches; api files[] block contains the 'Starfield Engine Fixes - Game version 1.15.216' branch chain AND the (truncated) 1.16.244 branch chain. Installed file = 'Starfield_Engine_Fixes_-_Game_version_1.16.244_20.2_ZTp3Rjj84.zip' (version 20.2.0.0). meta.ini nexusFileStatus=1, version=20.2.0.0, newestVersion=20.2.0.0 — exact match, no drift. Essence walk: SFSE/Plugins/StarfieldEngineFixes.dll (1.51 MB) + StarfieldEngineFixes.ini (28.9 KB config) — classic SFSE DLL plugin layout. The 'Save Cleaner - Highly Experimental' optional file (referenced in files[] block, updated through 2026-05-16) is NOT installed by BB84 — only the core fixes DLL is present. User hypothesis (folder name '1.16.244' is just a curator annotation on a perfectly-current mod) is fully validated: the version IS current, the game-version branch IS matched to local Starfield 1.16.244, and the listing IS healthy. Description desc-match was a false positive likely triggered by words like 'experimental', 'highly experimental', or the long fixes-list vocabulary. | Keep enabled. NO action needed — fully healthy and current. Suggest renaming BB84's MO2 folder from 'Starfield Engine Fixes - Game version 1.16.244' to something stable like 'Starfield Engine Fixes - SFSE [1.16.244 branch]' to avoid the folder name itself triggering desc-match classifiers on future runs (the embedded game version in the folder name is the reason the classifier got confused — folder names are sometimes scanned alongside description text in heuristic pipelines). |
| [The Real Elevator for Starfield](https://www.nexusmods.com/starfield/mods/10904) | 10904 | API status=published, available=true, fetched today (2026-06-25). Installed version 2.0.0.0 == newest 2.0.0.0. nexusFileStatus=1 (current). Mod has 296 endorsements, 41k downloads. Author still active on Nexus with two other published Starfield mods linked from the description. The 21-month-old timestamp is real but reflects a stable, complete mod that hasn't needed updates - it ships TheRealElevator.esm + 5 .psc/4 .pex Papyrus scripts that monkey-patch ElevatorMasterScript / MovingPlatformMasterScript and stay valid as long as game scripts aren't restructured. | KEEP installed. No action required. Optionally: feed the audit classifier a negative example so '(Old version)' file-list entries and [s]untested[/s] strikethroughs in POI lists stop triggering desc-match. Mod itself is fully healthy. |
| [Trees Rescaled](https://www.nexusmods.com/starfield/mods/11731) | 11731 | API status=published, available=true, fetched today. file_updates array is empty - this is a single-release mod that has never needed a patch. 749 endorsements, 36k downloads. Mod is a pure-asset .esm (360KB) that overrides tree scale records - it does not depend on game-version-specific scripts or .dll. Installed version 1.0.0.0 == Newest 1.0.0.0 (per inventory). nexusFileStatus=1 (current). | KEEP installed. No action required. Optionally feed the audit classifier a version-format equivalence rule: treat /V?(\\d+(\\.\\d+){0,3})/ semantically (V1.0 == 1.0 == 1.0.0 == 1.0.0.0). The 21mo age is normal for a stable pure-asset record-edit mod that needs no maintenance. |
| [Permanent POIs](https://www.nexusmods.com/starfield/mods/13899) | 13899 | Nexus API returns status='published', available=true, mod_id=13899, version='1.01' on the page with file 1.02 as MAIN (uploaded 2025-06-17, 8 days fresh in this audit window), 57,430 downloads / 239 endorsements, author polvovoss member_id 192735146 (still active). meta.ini nexusFileStatus=1 (healthy), lastNexusQuery=2026-06-25T01:56:13Z is current. The 'abandoned' regex match in classifier was a FALSE POSITIVE: the words 'Abandoned Farm' and 'Abandoned Mining Complex' in nexusDescription are IN-GAME POI NAMES that the mod renames ('I changed some of names slightly... "Abandoned Farm" has become "Abandoned Chemical Farm" and an "Abandoned Mine" became "Abandoned Mining Complex"'), not lifecycle status of the mod itself. Essence walk: PermanentPOIs.esm only (no scripts, no archives, no DLL) — small static record-edit plugin for POI placements. Installed version f1.01 matches inventory newest=f1.01 (a soft drift behind page 1.02 = 'Added Deserted UC Listening Post in Eta Cassiopeia' — minor content addition, not a fix). | Keep enabled, treat as fully healthy. OPTIONAL minor refresh: download 1.02 (the only delta is one additional POI in Eta Cassiopeia) for completeness, but 1.01 is not a defect. Update classifier regex to NOT match 'abandoned' inside quoted in-game location names — or, better, drop description-keyword 'abandoned/removed' regex as a primary signal and rely on nexusFileStatus + api_status fields which are already correct here. |

---

## 3. Yellow (低紧迫性版本陈旧)

以下 mod 是 published + available 但版本陈旧或久未更新。**不是 bug**，按 curator 时间窗口处理。

### 3.1 YELLOW-RECLASSIFIED (原 Red 被版本格式误伤，归一化后需 spot-check)

| Mod | Modid | 安装版本 | 最新版本 | 状态 |
|---|---:|---|---|---|
| [Starfield Performance Optimizations](https://www.nexusmods.com/starfield/mods/104) | 104 | `1.1.0.0` | `1.2` | published |
| [Darker Nights](https://www.nexusmods.com/starfield/mods/9616) | 9616 | `1.1.0.0` | `1.0` | published |
| [Immersive Landing Ramps 2.0 Chinese translation](https://www.nexusmods.com/starfield/mods/11653) | 11653 | `d2025.7.3.0` | `1.0` | published |

### 3.2 YELLOW (genuine — 12mo+ 无更新但 published)

| Mod | Modid | 安装版本 | 最新版本 | 最后更新 |
|---|---:|---|---|---|
| [Skill Challenges Removed](https://www.nexusmods.com/starfield/mods/9893) | 9893 | `d2025.7.10.0` | `2.0` | 2024-06-19 |
| [SKK Fast Start New Game (Starfield)V014 - Simplified Chinese Translation](https://www.nexusmods.com/starfield/mods/12927) | 12927 | `1.0.0.0` | `014` | 2025-01-07 |
| [Luma - Native HDR and more](https://www.nexusmods.com/starfield/mods/4821) | 4821 | `d2024.10.1.0` | `778860b` | 2025-03-15 |
| [Grendel SMG suppressor replacement](https://www.nexusmods.com/starfield/mods/3094) | 3094 | `1.0.0.0` | `1.1` | 2025-04-28 |
| [Dark Universe - Takeover - Traditional Chinese](https://www.nexusmods.com/starfield/mods/11628) | 11628 | `1.1.0.0` | `1.0.1` | 2025-05-11 |
| [Show XP on Loading Screens](https://www.nexusmods.com/starfield/mods/5616) | 5616 | `1.2.0.0` | `2.0` | 2025-05-22 |
| [Starvival - Immersive Survival Addon - Chinese translate cn](https://www.nexusmods.com/starfield/mods/14090) | 14090 | `f10.8` | `10.8.0` | 2025-06-09 |
| [No More Tiers Remastered](https://www.nexusmods.com/starfield/mods/9848) | 9848 | `1.0.0.0` | `1.4` | 2025-07-21 |
| [Immersive Cargo Halls](https://www.nexusmods.com/starfield/mods/14217) | 14217 | `1.0.0.0` | `1.0.1` | 2025-07-22 |
| [ZSW - Airlocks](https://www.nexusmods.com/starfield/mods/12532) | 12532 | `d2025.8.23.0` | `.0.9.5` | 2025-07-24 |
| [Permanent POIs - Evil Beyond](https://www.nexusmods.com/starfield/mods/14059) | 14059 | `0.94.0.0` | `1.02` | 2025-09-18 |
| [Permanent POIs - Rogue Science](https://www.nexusmods.com/starfield/mods/14278) | 14278 | `1.0.0.0` | `1.05` | 2025-10-21 |
| [Community Spaceship Expansion](https://www.nexusmods.com/starfield/mods/14174) | 14174 | `1.0.0.0` | `1.3.2` | 2025-11-12 |

---

## 4. Healthy (95 个，紧凑表)

<details><summary>展开查看完整健康 mod 列表</summary>

| MO2 folder | Modid | 版本 (Installed → Latest) |
|---|---:|---|
| `Address Library` | [3256](https://www.nexusmods.com/starfield/mods/3256) | `22.0.0.0` → `22` |
| `Aio Ultimate ChargenMenu Presets` | [8686](https://www.nexusmods.com/starfield/mods/8686) | `1.2.0.0` → `v1.2` |
| `Astrogate 4.0 Beta` | [9363](https://www.nexusmods.com/starfield/mods/9363) | `d2025.7.11.0` → `5.8` |
| `ATLAS Clothing - Advanced Techwear 1.2` | [12704](https://www.nexusmods.com/starfield/mods/12704) | `1.2.0.0` → `1.2` |
| `Atmosphere Affects Radiation` | [14298](https://www.nexusmods.com/starfield/mods/14298) | `1.0.0.0` → `1.0` |
| `Baka Achievement Enabler - AddLib 22` | [658](https://www.nexusmods.com/starfield/mods/658) | `7.0.0.0` → `7.0.0` |
| `Baka Quick Full Saves - AddLib 22` | [1750](https://www.nexusmods.com/starfield/mods/1750) | `7.0.0.0` → `7.0.0` |
| `Barefoot Footstep Sounds for Shoeless Clothing` | [7653](https://www.nexusmods.com/starfield/mods/7653) | `1.1.0.0` → `1.1` |
| `Bullet hole Impact 2.0` | [3026](https://www.nexusmods.com/starfield/mods/3026) | `2.0.0.0` → `2.0` |
| `Cassiopeia Papyrus Extender` | [10896](https://www.nexusmods.com/starfield/mods/10896) | `9.4.0.0` → `9.4` |
| `CharGenMenu - SFSE 1-16-242` | [6850](https://www.nexusmods.com/starfield/mods/6850) | `1.1.0.22` → `1.1.0.22` |
| `CharGenMenu Simplified Chinese` | [6863](https://www.nexusmods.com/starfield/mods/6863) | `1.1.0.15` → `1.1.0.15` |
| `Clean Chinese Fonts` | [391](https://www.nexusmods.com/starfield/mods/391) | `1.0.0.0` → `1.0` |
| `Clean Vanilla Hitmarker` | [1689](https://www.nexusmods.com/starfield/mods/1689) | `1.5.0.0` → `1.5` |
| `Dark Universe - Crossfire - SC` | [10276](https://www.nexusmods.com/starfield/mods/10276) | `2.1.0.0` → `2.1.0` |
| `Dark Universe - Takeover` | [11045](https://www.nexusmods.com/starfield/mods/11045) | `1.1.0.0` → `2.1.0` |
| `Detailed Reference Info` | [7589](https://www.nexusmods.com/starfield/mods/7589) | `10.0.0.0` → `10.0` |
| `Enhanced Lights and FX` | [54](https://www.nexusmods.com/starfield/mods/54) | `0.1.1.0` → `0.1.1` |
| `Enhanced Lights and FX CHS` | [11794](https://www.nexusmods.com/starfield/mods/11794) | `0.1.1.0` → `0.1.1` |
| `Fallout Radio` | [3839](https://www.nexusmods.com/starfield/mods/3839) | `1.0.0.0` → `1.0` |
| `Immersive Landing Ramps` | [8093](https://www.nexusmods.com/starfield/mods/8093) | `3.0.0.0` → `3.1.0` |
| `Immersive Ship Greetings` | [14231](https://www.nexusmods.com/starfield/mods/14231) | `1.0.0.0` → `1.0` |
| `Immersive Star Colours` | [14274](https://www.nexusmods.com/starfield/mods/14274) | `1.1.0.0` → `1.0.0` |
| `Immersive Starborn Temples` | [10972](https://www.nexusmods.com/starfield/mods/10972) | `1.0.0.0` → `1.0` |
| `Left Align XP Bar` | [95](https://www.nexusmods.com/starfield/mods/95) | `f1.05` → `1.06` |
| `Less Rocks - GRiNDTerra` | [13094](https://www.nexusmods.com/starfield/mods/13094) | `f1.02` → `2.0` |
| `Limitless Ship Builder` | [12184](https://www.nexusmods.com/starfield/mods/12184) | `1.0.0.0` → `1.0` |
| `Milkdrinker's New Atlantis Mesa Trees Reborn` | [13137](https://www.nexusmods.com/starfield/mods/13137) | `1.0.0.0` → `1.0` |
| `More Immersive Landings And Takeoffs` | [2835](https://www.nexusmods.com/starfield/mods/2835) | `1.4.0.0` → `1.4.1` |
| `More Visualized Docking` | [4679](https://www.nexusmods.com/starfield/mods/4679) | `1.3.0.0` → `1.3.2` |
| `NAT Station Lake Windows` | [14158](https://www.nexusmods.com/starfield/mods/14158) | `2.0.0.0` → `2.1.0` |
| `No Sound In Space` | [3156](https://www.nexusmods.com/starfield/mods/3156) | `0.2.0.0` → `0.2` |
| `Non-Lethal Framework` | [7812](https://www.nexusmods.com/starfield/mods/7812) | `3.0.2.0` → `3.2` |
| `Non-Lethal Framework - SC` | [8615](https://www.nexusmods.com/starfield/mods/8615) | `1.0.0.0` → `1.0` |
| `Paper Books` | [3139](https://www.nexusmods.com/starfield/mods/3139) | `1.0.0.0` → `1.0.0` |
| `Perk Auto Level - SFSE 0-2-21` | [5154](https://www.nexusmods.com/starfield/mods/5154) | `1.2.0.0` → `1.2` |
| `Permanent POIs - Darkness Beckons` | [14188](https://www.nexusmods.com/starfield/mods/14188) | `f1.02` → `1.02` |
| `Places Of Intrigue - GRiNDTerra` | [11530](https://www.nexusmods.com/starfield/mods/11530) | `3.5.0.0` → `5` |
| `Quick Trade` | [8171](https://www.nexusmods.com/starfield/mods/8171) | `1.0.9.2` → `1.0.9.2` |
| `Real Flashlight - Bigger Size Plugin` | [570](https://www.nexusmods.com/starfield/mods/570) | `1.2.0.0` → `1.2` |
| `Real Fuel - BETA` | [13306](https://www.nexusmods.com/starfield/mods/13306) | `1.1.2.0` → `1.3.1` |
| `Revelation - Main Quest Temple Overhaul` | [10418](https://www.nexusmods.com/starfield/mods/10418) | `1.0.0.0` → `1.5.0` |
| `RRL OBJECTS - Rabbit's Real Lights Landing Pads` | [11541](https://www.nexusmods.com/starfield/mods/11541) | `1.0.0.0` → `1.0` |
| `RRLC - Rabbit's Real Lights Cydonia` | [11224](https://www.nexusmods.com/starfield/mods/11224) | `1.0.1.0` → `1.0.1` |
| `RRLG - Rabbit's Real Lights Gagarin` | [11076](https://www.nexusmods.com/starfield/mods/11076) | `1.0.1.0` → `1.0.1` |
| `RRLHT - Rabbit's Real Lights HopeTown` | [11381](https://www.nexusmods.com/starfield/mods/11381) | `1.0.0.0` → `1.0` |
| `RRLN - Rabbit's Real Lights Neon` | [11498](https://www.nexusmods.com/starfield/mods/11498) | `1.0.0.0` → `1.0` |
| `RRLNA - Rabbit's Real Lights New Atlantis` | [10874](https://www.nexusmods.com/starfield/mods/10874) | `1.3.0.0` → `1.4` |
| `RRLNH - Rabbit's Real Lights New Homestead` | [11590](https://www.nexusmods.com/starfield/mods/11590) | `1.0.0.0` → `1.0` |
| `Seamless Grav Jump 2.2 - Gravity Well Version` | [9666](https://www.nexusmods.com/starfield/mods/9666) | `2.2.0.0` → `2.2` |
| `Seek Out Stores - Conner's Cut` | [5995](https://www.nexusmods.com/starfield/mods/5995) | `1.4.0.0` → `1.4` |
| `Ship Vendor Framework` | [10057](https://www.nexusmods.com/starfield/mods/10057) | `1.5.4.0` → `1.10.0` |
| `Show Read Books` | [8042](https://www.nexusmods.com/starfield/mods/8042) | `1.0.0.0` → `1.0` |
| `SKKFastStartNewGame` | [5971](https://www.nexusmods.com/starfield/mods/5971) | `14.0.0.0` → `15` |
| `Smart Aiming - Third to First Person (Updated) ini` | [11706](https://www.nexusmods.com/starfield/mods/11706) | `1.0.0.0` → `5.0.0` |
| `Spacewalk With A Purpose 0.2.2` | [10377](https://www.nexusmods.com/starfield/mods/10377) | `0.2.2.0` → `0.2.2` |
| `Starfield anomaly style scope overhaul` | [1949](https://www.nexusmods.com/starfield/mods/1949) | `0.1.0.0` → `0.1` |
| `Starfield Community Patch - Traditional Chinese` | [11795](https://www.nexusmods.com/starfield/mods/11795) | `1.0.0.0` → `1.0` |
| `Starfield Extended - Craftable Quality - SC` | [8660](https://www.nexusmods.com/starfield/mods/8660) | `f4.02-FM` → `v4.1.0` |
| `Starfield Extended - Craftable Quality Shattered` | [5721](https://www.nexusmods.com/starfield/mods/5721) | `f4.02-FM` → `v4.1.0` |
| `Starfield HD Overhaul part 02` | [5124](https://www.nexusmods.com/starfield/mods/5124) | `f3.09` → `3.14` |
| `Starfield Locomotion Innovation Mod - SLIM` | [4588](https://www.nexusmods.com/starfield/mods/4588) | `0.3.1.0` → `0.3.1` |
| `Starfield Shader Injector - SFSE 1-16-236` | [5562](https://www.nexusmods.com/starfield/mods/5562) | `1.10.0.0` → `1.9` |
| `Starshake - Vizualized Recoil` | [10131](https://www.nexusmods.com/starfield/mods/10131) | `2.0.0.0` → `2.1.0` |
| `StarUI Configurator` | [5467](https://www.nexusmods.com/starfield/mods/5467) | `1.1.0.0` → `1.1` |
| `StarUI HUD` | [3444](https://www.nexusmods.com/starfield/mods/3444) | `1.3.0.0` → `1.3` |
| `StarUI HUD - SC` | [3474](https://www.nexusmods.com/starfield/mods/3474) | `1.3.0.0` → `1.3` |
| `StarUI Inventory` | [773](https://www.nexusmods.com/starfield/mods/773) | `2.4.1.0` → `2.4.1` |
| `StarUI Inventory - SC` | [804](https://www.nexusmods.com/starfield/mods/804) | `2.4.0.0` → `2.4` |
| `StarUI Outpost` | [5766](https://www.nexusmods.com/starfield/mods/5766) | `1.3.0.0` → `1.3` |
| `StarUI Ship Builder` | [6402](https://www.nexusmods.com/starfield/mods/6402) | `1.3.0.0` → `1.3` |
| `StarUI Ship Builder - SC` | [11808](https://www.nexusmods.com/starfield/mods/11808) | `1.3.0.0` → `1.3` |
| `StarUI Workbench` | [4966](https://www.nexusmods.com/starfield/mods/4966) | `1.2.0.0` → `1.2` |
| `StarUI Workbench - SC` | [5153](https://www.nexusmods.com/starfield/mods/5153) | `1.1.0.0` → `1.1` |
| `Starvival - Immersive Survival Addon - New` | [6890](https://www.nexusmods.com/starfield/mods/6890) | `11.0.0.0` → `12.4.6` |
| `Take Your Time - Shattered Space` | [10419](https://www.nexusmods.com/starfield/mods/10419) | `1.0.0.0` → `1.5.0` |
| `The Gang's All Here` | [7469](https://www.nexusmods.com/starfield/mods/7469) | `4.1.0.0` → `4.2` |
| `Trainwreck SFSE` | [5068](https://www.nexusmods.com/starfield/mods/5068) | `1.4.0.0` → `1.4.0` |
| `TrueVision Shattered Space DLC` | [13987](https://www.nexusmods.com/starfield/mods/13987) | `1.0.1.0` → `1.0.1` |
| `UC Military Overhaul - All-In-One` | [11350](https://www.nexusmods.com/starfield/mods/11350) | `2.1.0.0` → `2.2` |
| `UC Military Overhaul - Complete Edition` | [12085](https://www.nexusmods.com/starfield/mods/12085) | `1.2.0.0` → `1.3` |
| `UC Surplus Expanded - Immersive` | [7205](https://www.nexusmods.com/starfield/mods/7205) | `1.2.0.0` → `1.3` |
| `UCMO - Navy Fatigues Skin Pack (Gloves)` | [12458](https://www.nexusmods.com/starfield/mods/12458) | `1.0.0.0` → `1.0` |
| `UCMO - Spec Ops Skin Pack` | [11819](https://www.nexusmods.com/starfield/mods/11819) | `1.1.0.0` → `1.2` |
| `UCMO - Vanguard Pilot Skin Pack` | [11702](https://www.nexusmods.com/starfield/mods/11702) | `2.1.0.0` → `2.1` |
| `Undelayed Menu - Latest Version` | [404](https://www.nexusmods.com/starfield/mods/404) | `1.0.6.0` → `1.0.6` |
| `UnlimitedMannequins` | [6291](https://www.nexusmods.com/starfield/mods/6291) | `1.0.0.0` → `1.0` |
| `Usable bench press and pull up bar` | [10301](https://www.nexusmods.com/starfield/mods/10301) | `1.0.0.0` → `1.0` |
| `Usable bench press and pull up bar CN` | [10784](https://www.nexusmods.com/starfield/mods/10784) | `1.0.0.0` → `1.0` |
| `Useful Brigs` | [8139](https://www.nexusmods.com/starfield/mods/8139) | `5.0.1.0` → `6.1` |
| `Useful Brigs - SC` | [8614](https://www.nexusmods.com/starfield/mods/8614) | `1.0.0.0` → `1.0` |
| `VASCO-9000 Voice Replacement` | [3306](https://www.nexusmods.com/starfield/mods/3306) | `1.0.0.0` → `1.0` |
| `Visible Chronomark Watch` | [8092](https://www.nexusmods.com/starfield/mods/8092) | `2.0.0.0` → `2.0.0` |
| `Weapons of Fate (Ballistics Overhaul)` | [162](https://www.nexusmods.com/starfield/mods/162) | `1.1.1.0` → `1.1.1` |
| `Xeno Master Addon Trade Authority can sell XM Items` | [10380](https://www.nexusmods.com/starfield/mods/10380) | `1.1.4.0` → `1.2.77` |

</details>

---

## 5. 分类器改进项 (来自深度调查的反馈)

以下是从 deep fate investigation 中暴露的原 fan-out fixer 分类器假阳性来源，**应该在下次 staleness audit 的 fixer prompt 中预先 fix**。

### 5.1 Version comparator artifact (~80 个 pseudo-Red 的根因)

MO2 把版本号归一化为 4 段（`1.0.0.0`），Nexus 通常存 2 段（`1.0` / `V1.0`）。原 fixer 用字符串相等比较，所有这类对都被误判为 Red。修复（已 inline 实现）：
- Strip leading `V`/`v`
- Trim trailing `.0` segments
- Recognize BB84 build-stamp pattern `d\\d{4}\\.\\d{1,2}\\.\\d{1,2}\\.\\d+` and skip semver compare (use file_id/hash instead)

### 5.2 In-game vocabulary collision with mod-lifecycle vocabulary

Desc-regex 匹配 `abandoned|removed|discontinued` 等会把游戏内 POI 名（如 `Abandoned Farm`、`Abandoned Mining Complex`）误判为 mod 弃坑信号。修复建议：
- 只匹配特定上下文（句首 / 跟 `mod`/`this mod` 相邻）
- 排除 POI/location 命名上下文
- 加 negative-example denylist：`Abandoned Farm`, `Abandoned Mining Complex`, `Abandoned Outpost` 等已知 starfield POI 名

### 5.3 Folder name embedding game-version annotation

BB84 习惯把游戏版本写进 mod folder 名（如 `Starfield Engine Fixes - Game version 1.16.244`）。fixer 不应该把 MO2 folder name 喂进 desc-regex；只用 Nexus API 返回的 description 字段。

### 5.4 Multi-variant mod 误报 'update available'

Eyes of Beauty 类 mod 在 Nexus 上有多个 file_id 对应不同变体（Replacer-only OPTIONAL vs 完整 .exe Installer MAIN）。比较版本时如果用 mod-page-version 比 file-version 会跨变体误报。修复：按 file_id / file_name 跟踪 variant lineage，不要用 page-level version。

### 5.5 ARCHIVED/OPTIONAL 子文件的描述文本不应触发 mod-lifecycle 信号

子补丁的 file_description (如 'THIS PATCH WILL BE DELETED AFTER THE 2.3.0 RELEASE') 描述的是单个 patch 被并入父 mod，不是整个 mod 弃坑。修复：desc-regex 只 scope 到 MAIN-category 文件，不扫描 ARCHIVED/OPTIONAL/UPDATE 文件。

---

## 6. 方法论 & 数据来源

### 调查方法
- 第一遍 fan-out fixer (4 lane, modulo split): 调用 Nexus API `/v1/games/starfield/mods/{modid}.json` + `/files.json`，简单分类 Red/Yellow/Green
- 第二遍 fan-out fixer (4 lane, 12 mod 重点深度调查): 每 mod 走完整 fate investigation — 同作者 republish 检查 + 站外延续检查 + 本地 essence 分析 + 4+ outcome 分类
- Orchestrator inline merge + version normalization + 假阳性 reclassification → 最终 verdict

### 相关 KB 记录
- `install-planning.audit-grade-mod-fate-investigation.v1` — audit-grade fate investigation methodology (codified during this audit)
- `mod-evaluation.investigating-pulled-mods.v1` — continuity tracing
- `install-planning.mod-update-post-state-discipline.v1` — intent-aware mutation discipline
- `archive-precedence.stale-ck-extract-loose-files.v1` — stale CK extract methodology
- `debugging.asymmetric-evidence-self-falsify.v1` — diagnostic discipline

### Raw 数据
- 4 lane classification: `lane-{A,B,C,D}-results.json`
- 4 lane deep fate: `lane-{A,B,C,D}-fate-results.json`
- Merged 总表: `merged-audit-results.json`
- Per-modid API cache: `api-cache/<modid>.json`
- 全部位于 `D:\awesome-bgs-mod-master\.opencode\artifacts\bb84-starfield-audit-2026-06-25\`

---

## 7. 下一步

此报告是 Lane 2 的产物。下一步进入 **Lane 3 (curator-driven mod 审查 + plugins.txt 排序优化)**:
- 用本报告的 Section 1 (10 个真需要决策的 mod) 作为切入点
- 按 priority (heavy papyrus → 大型机制/剧情 → 小改/数据) 对当前所有 enabled mod 做审查
- 用 xEdit 实测 conflict (Lane 5 并入 Lane 3)
- 决定哪些 mod 需要 patch 冲突 + 怎么优化 plugins.txt 排序
- multi-perspective consultation 设计 Lane 3 audit framework

Lane 4 (汉化批量重译) 保持最后，等 Lane 3 mod 集合稳定下来后统一跑批。
