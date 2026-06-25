# BB84自用2 Starfield Modpack — Dev Log

> 整合包维护日志。重要变更（mod 增删、版本升级、配置调整、问题诊断、SFSE / Address Library 升级）写入新条目。最新条目放文件顶部。

---

## 2026-06-24 ## 整合包首次系统 audit + 备注 substrate 构建

### 背景

通过本轮真实 audit 同时丰富 `bgs-modding-superpowers` plugin 的 skills + KB。

### 启动时 substrate snapshot

| 维度 | 实测 |
|---|---|
| 总 mod 数 | 393 |
| Separators | 31 |
| Nexus mods（modid != 0 + repository=Nexus） | 172 |
| CC 原版（`*-cc` 文件夹） | 27 unique |
| CC 汉化（`*-cc - SC`） | 27 |
| Manual 安装 | 88 |
| NoMeta（去除 separator 后剩余） | 待补 |
| MO2 版本 | 2.5.3 |
| 活跃 profile | `BB84自用2`（中文，@ByteArray 编码） |
| SFSE 当前 | 0.2.20 / runtime 1.15.222（`sfse_1_15_222.dll`） |
| SFSE 最新（silverlock.org） | 0.2.21 / runtime 1.16.244 |
| Address Library 当前 | v19 |
| Address Library 最新（Nexus #3256） | v22 |

### 本轮执行项

- **Task 1a** — 172 Nexus mods 写入中文备注：基于 meta.ini 已缓存的 `nexusDescription`，剥 BBCode/HTML，提炼 1-2 句中文摘要写入 `notes=`；如 `version != newestVersion` 在 notes 头加 `[UPDATE→vX] ` 标记。4 fixer lanes parallel。
- **Task 1b** — 27 unique CC mods 反查 Bethesda Creations marketplace 真名：从 `.esm` 名 Exa 搜索 → 写入原版 + `- SC` 两个文件夹的 `notes=`。3 fixer lanes parallel。
- **Task 2** — 本 dev-log + release-changelog substrate（项目本地 + plugin 仓库镜像）。
- **Task 3** — 更新审计：写入 `docs/mod-update-audit.md`，含 Nexus version-diff + CC 静态状态。与 Task 1a 的 `[UPDATE→vX]` 标记共同构成"双写"实现。
- **Task 4** — SFSE 0.2.20 → 0.2.21 升级人机协作（等 Nexus API key 后启动）。

### 探索 / 未知项（决定下一轮 plugin 工作方向）

1. **agent 直连 Nexus 下载是否可行**：Premium API key 路径 vs 免费用户 sessdata cookie fallback。
2. **MO2 update-check 触发**：是否有 MCP 接口可以触发 lastNexusQuery 刷新，还是必须 MO2 GUI 启动并人工触发 `Tools → Check All for Updates`。
3. **SFSE 这类游戏根（非 MO2 VFS）落地工具**的安全人机协作 workflow shape：下载 → 7z 解压 → 备份 → 用户确认 → 替换 → 验证。
4. **MO2 MCP 暴露的 product 问题**：(1) Starfield 误检为 fallout4；(2) `@ByteArray` 中文 profile 名解码后路径写入仍传 `\xe8...` 字面转义导致 ENOENT。

### 执行结果

#### Task 1a — Nexus mods 备注（172/172 ✓ 0 失败）

- 4 fixer lanes × 43 mods 并行，全部 UTF-8 no BOM 写入 `notes=` 字段
- **30 个 mod 有版本不一致**（`version != newestVersion`，详见 `mod-update-audit.md`）
- 备注实例：
  - `Address Library`: `为 SFSE DLL 插件提供版本独立的 Address Library 数据库...`
  - `Astrogate 4.0 Beta`: `[UPDATE→4.0.1.0] 提供飞船 FTL/Supercruise、autopilot 与系统内/星系间航行体验...`
  - `Souls of Cities 4.4`: `[UPDATE→7.0.0.0] 以 SFSE 框架替换/增强城市 crowd NPC 系统...`
- 工作流：每个 fixer 走 4 phase — extract JSON → translate JSON → write script → readback verify
- artifact: `D:\awesome-bgs-mod-master\.opencode\artifacts\bb84-starfield-audit-2026-06-24\nexus-lanes\lane-*-{extract,notes,readback}.{json,txt}`

#### Task 1b — CC mods 备注（132/132 ✓ 0 失败）

- 3 fixer lanes × 44 folders 并行，含 web search 反查 Bethesda Creations marketplace 名
- **79 个 CC 原版无 meta.ini → 创建**（含 `[General]\nnotes=...\n[installedFiles]\nsize=0\n`）
- **53 个 SC 变体改写已有 meta.ini 的 `notes=` 字段**
- **125/132 (94.7%) 成功反查到 marketplace 名**；6 个 stem 未找到，notes 标记 `(未找到)`：
  - `No Loading Ship`、`astrogate`、`bubegg`、`satou_sr2_destroy01`、`tankgirlsxenologyexpanded`、`rvexplore`
- 备注实例：
  - `adwryos-cc`: `[CC] 《RYOS (Roll Your Own Start)》 — 可延后、跳过或自定义主线开局...`
  - `adwryos-cc - SC`: `[CC·汉化版] RYOS (Roll Your Own Start) — 延后、跳过或自定义主线开局...`
  - `aseveil-cc`: `[CC] 《Beyond the Veil》 — 围绕神秘陌生人与受未知力量影响的星系展开的剧情任务。`
- artifact: `.opencode/artifacts/bb84-starfield-audit-2026-06-24/cc-lanes/cc-lane-*-{research,readback}.{json,txt}`

#### Task 2 — Substrate ✓

- `D:\Starfield MO2\docs\dev-log.md`（本文件） + `release-changelog.md` 已创建
- 镜像至 `D:\awesome-bgs-mod-master\docs\modpack-dev-logs\bb84-starfield\` 含 README + mod-update-audit 镜像

#### Task 3 — Update audit ✓（双版本：缓存 + fresh）

**缓存版** (`docs/mod-update-audit.md` summary 节)：
- 30 个 UPDATE-tagged mods（基于 MO2 ~2025-08 cache）
- 6 个 CC 未找到 marketplace 名

**Fresh refresh 版**（Option B 工作流首次实战）：
- 1 fixer 走 172 个 Nexus mods 直 API 调用 `/v1/games/starfield/mods/{id}.json`，写回 `newestVersion` / `nexusFileStatus` / `lastNexusQuery` / `lastNexusUpdate`
- 0 API 错误，~173 calls，API budget 余额 hourly 1825 / daily 19825
- **162 个 mod 实际有更新**（远大于缓存的 30 — stale 数据漏了 132 个！）
- **8 个 mod 在 Nexus 已 removed/hidden/not_published**：
  - `CharGenMenu` [not_published]
  - `Denser Vegetation - GRiNDTerra` [removed]
  - `ImmersiveDataSlates` [hidden]
  - `Just Random Vegetation Rock and Exotic Sizes - GRiNDTerra` [removed]
  - `OwlTech_Pathfinder` [hidden]
  - `Space Ship Landing Reloaded` [removed]
  - `VaruunTI Habs` [removed]
  - `Weapon Swap Stuttering Fix - AddLib 5` [hidden]
- artifact: `.opencode/artifacts/bb84-starfield-audit-2026-06-24/fresh-refresh-2026-06-24.json`

#### Task 4 — SFSE 0.2.20 → 0.2.21 升级 ✓

**起始状态**：Steam Starfield.exe 已自动升到 1.16.244（昨日），SFSE 落后在 0.2.20 (1.15.222 dll) — 实际无法启动游戏。

**Nexus API workflow（Premium 直接下载）**：
1. `GET /v1/games/starfield/mods/106/files.json` → 找到 file_id=67782 (MAIN, v0.2.21)
2. `GET /v1/games/starfield/mods/106/files/67782/download_link.json` → 7 CDN mirrors，选 Chicago premium
3. 下载 380962 bytes → `F:\Starfield Mods\Utilities\SFSE-106-0-2-21-1781567173.7z`（**实践 BB84 的 F:\ 收纳约定**）
4. 7-Zip 解压到 staging（**注意 7z 解到 `sfse_0_2_21/` 子目录，不 flat！**）
5. Diff vs game root：sfse_loader.exe 同 hash 跳过，sfse_1_16_244.dll 新增，readme/whatsnew hash 不同，sfse-0.2.21.tar.gz 是源码不进 game root
6. **4 文件备份**到 `D:\Starfield MO2\.backups\sfse-0.2.20_pre-0.2.21-update_2026-06-24_1804\`
7. COPY/REPLACE/DELETE → verify sha256 全 match

**Game root 终态**：`sfse_1_16_244.dll` + `sfse_loader.exe` + `sfse_readme.txt` + `sfse_whatsnew.txt`，与 Starfield 1.16.244 runtime 完美匹配。

**关键失败 + 修复教训**：
- 第一遍 PowerShell 脚本 `$name:` 字符串插值被 PS 当作变量解析挂掉；并且 print "copied" 发生在 if 块开头 BEFORE Copy-Item，**Copy 失败被静默吞掉但 print 已发**，导致 game root 一度处于"无 dll"危险状态（旧的删了，新的没拷上）
- 真实根因：7z 解压到 `sfse_0_2_21/` 子目录，脚本一直找 `$stagingDir\sfse_1_16_244.dll` 找不到（应该是 `$stagingDir\sfse_0_2_21\sfse_1_16_244.dll`）
- 修复：`Get-ChildItem -Recurse -Filter` glob 找真实路径；`$ErrorActionPreference = "Stop"` 让错误硬失败
- **教训应进 skill**：(a) 任何下载-解压-落地工作流默认 glob find 而非 hardcode path；(b) PowerShell 脚本头声明 strict mode；(c) print **AFTER** action confirms, not before

### Edge case / 限制

- **2 个空 notes**：`Fast Spacesuit Toggle` 与 `Starfield Community Patch` 因 `modid=0`（手动安装无 Nexus 集成）被分类器分到 Manual 桶，未被任何 fixer 处理。SCP 本是 Nexus #2851，可在后续 API refresh 时识别并补写。
- **89 个 Manual + NoMeta mods 未处理**：本轮范围限于 Nexus + CC，Manual 安装的 mods（含 modders' resources、前置依赖、手装 Nexus）未写 notes。
- **30 个 UPDATE-tag 基于 2025-08 缓存**，2026-06 的实际 Nexus state 未知；fresh refresh pass 是后续工作。

### 本轮发现 / 学到的（待固化）

1. **MO2 MCP bug #1**: Starfield 被检测为 fallout4。sidecar 的 game-name → MCP game enum 映射缺 Starfield。
2. **MO2 MCP bug #2**: `@ByteArray(...)` decode 后路径写入 fs 仍传字面 `\xe8...` 转义，导致 ENOENT。Chinese-named profile 失败。
3. **`nexusDescription` 缓存在 meta.ini 中** — 任何曾被 MO2 GUI Tools → Check All for Updates 过的 mod 都有完整描述缓存。**Task 1a 完全可零联网**。
4. **Option B 是 Nexus refresh 的最优解**（per explorer 报告）：direct API call + `mo2_edit_meta`，无 Premium 需求，20k/日预算，~173 calls 全 sweep。
5. **CC mods 79 原版无 meta.ini** — `make_mods_from_cc.py` 不生成 meta。需 fixer 创建。
6. **CC marketplace 名查找 94.7% 成功率**（Exa search "Bethesda Creations Starfield <stem>"）— 6 个失败的 stem 多为 modder 资源或 delisted CC。
7. **Console UTF-8 渲染陷阱**：PowerShell 默认 GBK codepage 把 UTF-8 字节渲染成乱码。`[Console]::OutputEncoding = [Text.Encoding]::UTF8` 必须在脚本头声明。
8. **CC 的下载/安装必须留给用户**（comment #3）：游戏内 UX 操作，agent 不可代劳。`bb84_plugins/Make-Starfield-CC-as-mods-in-MO2/make_mods_from_cc.py` 通用化后是物化步骤的 plugin asset。
9. **BB84 个人规则**（comment #4）：非 CC mods 下载到 `F:\Starfield Mods\<分类>\` — subjective 收纳约定，不强加他人。


### 后续 plugin 工作（本轮 audit 衍生）

- (Comment #3) **CC 整合通用规则**入 KB：所有 BGS 游戏 CC 内容 = 游戏内下载 → 退出游戏 → MO2 `overwrite/` 出现 → 用脚本物化为独立 mod。游戏内 UX 必须用户完成，agent 不可代劳。
- (Comment #3) `bb84_plugins/Make-Starfield-CC-as-mods-in-MO2/make_mods_from_cc.py` 通用化（去掉硬编码 Starfield / MO2 路径），移入 plugin `scripts/`。
- (Comment #4) **BB84 个人规则**入 subjective KB（不强加用户）：非 CC Starfield mod 下载到 `F:\Starfield Mods\<分类>\`。
- 上述 2 个 MCP bugs 补 KB + roadmap product-gap。

---

---

## 2026-06-24 [round-2] ## 后续修正 + xSE 级联升级 + pulled mod 调查

### P1 — notes / comments 字段修正
- 我原写错位置（写到 notes=）。MO2 GUI mod list 显示的是 `comments=` 字段，`notes=` 是 properties dialog Notes 标签的长文本。
- 迁移脚本：306 个 mod 的 `notes=` → `comments=`，全 UTF-8 no BOM，0 冲突。
- 教训进 `.opencode/memory/45-mo2-mcp-internals.md` rule 18 + `maintaining-modding-environments` skill 新节 "meta.ini comments= vs notes= field distinction"。

### P2a — SFSE 占位 dummy mod 同步
- BB84 个人约定：空 mod folder 含 `sfse_<binary-ver>\` 标记子目录 + 完整 nexus meta.ini，用于让 SFSE 二进制版本在 MO2 GUI 可见
- 重命名：`Starfield Script Extender 1-15-222` → `Starfield Script Extender 1-16-244`，内部 marker `sfse_0_2_18` → `sfse_0_2_21`
- modlist.txt 也跟着改

### P2b — Address Library v19 → v22
- Premium API `download_link.json` → Chicago CDN mirror，27 MB
- 41 .bin 文件（含新 `versionlib-1-16-244-0.bin` 5MB）替换 mod folder
- 旧 .bin 备份到 `.backups/addrlib-v19_pre-v22-update_2026-06-24_2029/`
- 修复了 SFSE Plugin Loader 启动对话框中 3 个 "address library needs to be updated" 报错的根因

### P2c — 9 个 SFSE 插件 mods 批量升级
| Mod | 旧版 | 新版 | 文件夹改名 |
|---|---|---|---|
| Baka Achievement Enabler | 6.0.0.0 | **7.0.0** | AddLib 18 → AddLib 22 ✓ |
| Baka Quick Full Saves | 6.0.0.0 | **7.0.0** | AddLib 18 → AddLib 22 ✓ |
| Cassiopeia Papyrus Extender | 5.0.0.0 | **9.4** | - |
| Detailed Reference Info | 7.1.0.0 | **10.0** | - |
| Smart Aiming - Third to First Person | 4.0.0.0 | **5.0.0** | - |
| Starfield Engine Fixes | 13.0.0.0 | **20.2** | "Game version 1.15.222" → "1.16.244" ✓ |
| Perk Auto Level | 1.1.0.0 | **1.2** | - |
| Souls of Cities | 4.4.0.0 | **10.0** | "4.4" → "10.0" ✓ |
| Starfield Shader Injector | 1.7.0.0 | **1.10** (实际是 fixer 拿到的 latest) | - |

API budget 余额 hourly 1952 / daily 19952。Premium download_link 总下载 ~7.1 MB。所有备份在 `.backups/<modName>-<oldver>_pre-<newver>-update_<时间戳>/`。

### P2-pulled-mods — 被作者下架/隐藏的 mod 调查 + 重发模式

#### CharGenMenu (Nexus #20, status=not_published) → 作者重发了

- **MO2 跟踪**：Nexus #20，version 1.1.0.20，author Expired6978
- **下架原因**：API 返回 `status=not_published`，无明确公告。但作者并未消失。
- **作者重发 ✓**：**Expired6978 (user 2950481) 在同名 Nexus #6850 重发了同一个 mod**
  - 最新版 1.1.0.22 / 2026-05-26 / file_id=66881 / 3 MB
  - 完全继承原 mod 的功能和 SFSE 依赖
  - 来自 #6850 的 v1.1.0.20 zip 文件名是 `CharGen v1-1-0-20-6850-1-1-0-20-1754930264.7z` — BB84 之前手动下载过，但 MO2 mod folder 的 meta.ini 还指 `modid=20`，所以 update-check 一直看 #20 的 not_published 状态。
- **修复建议**：改 MO2 mod folder meta.ini `modid=20` → `modid=6850`，然后 fresh refresh 拿当前数据，再升级到 1.1.0.22。
- **教训**：作者重发是真实模式。下次发现 mod `not_published` / `hidden`，**第一步先查 Nexus 同名同作者的其它 modid**，而不是直接找替代。

#### Weapon Swap Stuttering Fix (Nexus #2830, status=hidden) → 没重发，但有替代

- **MO2 跟踪**：Nexus #2830，version 1.1.3，author AntoniX (user 1133204)
- **下架原因**：`status=hidden` 状态意味着从 listings 隐藏但 URL 仍能访问。原作者最后更新 2023-11-23，仅支持游戏 1.8.86+。Steam 当前 1.16.244 — mod 实际已过时；作者推测因停止维护而隐藏（未明确声明）。
- **作者重发？** 没有。AntoniX35 在 GitHub 仍维护源码，但 Nexus 没新 modid。
- **第三方继续维护**：allmods.net 有 v1.2.0（支持 1.15.222），但不是作者发布渠道，且 1.15.222 也已过时。
- **不同思路的替代 mod ✓**：**Nexus #16464 "Weapon Swap Stutter Fix" by melik173**
  - 2026-04-22 发布，v1.0
  - **perk-based 方案**（不需要 SFSE plugin）— 完全不同的实现思路：从 HumanRace 添加 perk 检查 weapon mod keywords 而非 inventory read 修补
  - 兼容性：HumanRace + legendary object mod + "_template" object mod records 的 mod 会冲突
- **修复建议**：用户决定 — (a) 保留旧 mod #2830（仍能跑因 Address Library v22 含 1.16.244 bin）；(b) 切换到 #16464；(c) 都装看哪个更稳。
- **教训**：mod hidden 不一定意味着坏；可能只是作者停止维护。**下次先看 mod 是否仍可访问 + 第三方替代是否兼容当前游戏版本**。

### 新工作习惯进 skills（待 codify）
当发现 mod `status=not_published` / `hidden` / `removed`：

1. **先查作者重发**：Nexus 同名 mod 不同 modid (新建即可不同 modid)。同作者其它 Starfield mods 看是否有功能/标题接近的。
2. **再查第三方维护**：GitHub fork / allmods 镜像 / community wiki。
3. **再查替代实现**：不同作者、不同实现思路的同功能 mod。
4. **写 dev-log 备忘**：MOD 名 + modid + 状态 + 推测下架原因 + 调查结论。便于半年后回看。
5. **MO2 meta.ini modid 漂移**：从 #A 重发到 #B 后，原 MO2 mod folder meta.ini 仍指 #A，需要手动更新 modid 字段才能让 Option B refresh 拿到正确状态。


---

### Nexus 免 Premium / 免 APIKEY 认证路径调查结论

**调查目的**：找到无 API key 的 agent 可用 Nexus 下载路径。  

**调查路径**：

1. ✗ **简单 cookie 抽取 + API 调用**：Chrome 149 全部 51 个 nexus cookies 都是 `v20` 前缀 = **app-bound encryption** (Chrome 127+，2024-07 引入)。DPAPI 解密 `Local State` 拿到的 AES-256-GCM key 解不开 v20 (返回空 error)，因为 v20 需要 chrome.exe 进程签名 + Windows COM Elevation Service 二次 unwrap。普通 PowerShell 脚本拿不到 plaintext。
2. ✗ **匿名 Nexus API**：`/v1/games.json`、`/v1/users/validate.json` 全部返回 `401 Unauthorized`。没有 anonymous read endpoint。
3. ✗ **sessdata 等价 cookie**：实测无。Nexus 的认证机制是 Cloudflare WAF (`cf_clearance` cookie) + 服务端 session，不暴露给 client-side JS。
4. ⚠️ **Chrome `--remote-debugging-port` + CDP**：技术上可行，但每个 session 都需要重启 Chrome 带 debug 端口。侵入用户工作流。
5. ⚠️ **第三方 ABE 解密工具**（如 `xaitax/Chrome-App-Bound-Encryption-Decryption`）：需要往 Chrome elevation service 进程注入代码。技术行为类似 infostealer malware，**不推荐 codify 到我们的 skills**。
6. ✓ **Premium APIKEY**：当前 BB84 走这条，从 MO2 `ModOrganizer2_APIKEY` (Win Credential Manager) 读出。已 codified 到 `maintaining-modding-environments` skill。
7. ✓ **浏览器手动下载 → agent 接管 process**：用户在 Chrome 浏览器手动点击 "Manual Download"（经 Cloudflare 验证）→ 文件落到约定路径（如 `F:\Starfield Mods\<分类>\`）→ agent 检测到新文件后接管解压 / install / meta 写入。这是免 Premium 的**唯一安全 agent 友好路径**。

**结论**：免 Premium 用户无法做到 agent 全自动 Nexus 下载。推荐工作流：
- 用户：浏览器手动下载 (10-30 秒，含 Cloudflare 验证)，文件落到约定路径
- agent：监控约定路径 → 检测新文件 → 解压 → 验证结构（Data/ 前缀 flatten） → 备份现有 mod folder → 替换 → 写 meta.ini

这个**用户手动下载 + agent 自动 process** 的混合模式应该 codify 到 skill。免 Premium 用户用 agent 节省的不是下载步骤，而是后续的解压 / install / meta 维护 / cascade 升级追踪。

**Chrome cookies AES key vault**：`.opencode/artifacts/bb84-starfield-audit-2026-06-24/chrome-cookie-key.dpapi` 保留，供未来如果 Chrome 引入 v21 / 改回普通 DPAPI 或 v10/v11 旧版本测试时复用。51 个 nexus 加密 cookies 的 base64 vault 在 `%TEMP%\nexus-cookies-Default.json`。

---

### Round-2 fallout: separator/enable observability fixes

发现两层观测漏洞：
1. **Fixer 没自检**：替换文件但不验证 separator 归属 + enable 状态
2. **我没核实**：信任 fixer summary 而非 grep modlist.txt 验证多维度 state

#### Shader Injector + Perk Auto Level（已修复）
- `Starfield Shader Injector - SFSE 1-12-30` → `Starfield Shader Injector - SFSE 1-16-236` + ENABLED + 移到 SFSE 功能模组
- `Perk Auto Level - SFSE 1-8-86 Waiting For Update` → `Perk Auto Level - SFSE 0-2-21` + ENABLED + 移到 SFSE 功能模组
- Shader Injector v1.10 作者声明 "Supports 1.16.236 and beyond"
- Perk Auto Level v1.2 是 Nexus 最新发布版，SFSE 插件通过 Address Library v22 (含 1-16-244 bin) 自动绑定，应该工作

#### Luma 评论调查（结论：留 等待作者更新 不动）
Nexus #4821 评论页 1/39（2026-05~06 时间窗）：
- 2026-05-24 作者 Filoppi: "We are working on it"
- 2026-06-21 用户："It's been over a month at this point since the mod has worked"
- 没有 1.16.244 / 1.16.236 兼容声明的 release
- Nexus description 的 "compatible with Starfield 1.14.74" 真实不是 stale；最新 release 778860b 是 2025-03-15，那是 1.14.74 时代
- **结论**：Luma 当前确实坏（自 1.5 patch 以来），作者维护中但未 ship 1.16.244 build。**保持 DISABLED + 留在 等待作者更新 是正确状态**

#### CharGenMenu（重新分类到 等待作者更新）
Nexus #6850 changelog：
- v1.1.0.22 (2026-05-26): **"Added support for Game Version 1.16.242"** ← 只到 1.16.242
- v1.1.0.21: "Game Version 1.16.236 support"

**当前 Steam runtime 是 1.16.244 — 超出 CharGenMenu v1.1.0.22 支持范围**。Steam 论坛验证："Still waiting on CharGenMenu myself, only one popping an SFSE error box"。

我之前的"修复"（modid 20→6850 + 升到 1.1.0.22）拿到了最新版本但**新版本本身还不支持当前游戏 runtime**。这是 ReAct 失误的第二例 — 我没核实"latest published" ≠ "compatible with current runtime"。

操作：
- 文件夹改名 `CharGenMenu` → `CharGenMenu - SFSE 1-16-242`
- meta.ini comments 改为 [WAITING-FOR-1.16.244] 标记
- modlist.txt 移到 等待作者更新 separator + DISABLED

#### 当前 "等待作者更新" separator 终态
1. `Weapon Swap Stuttering Fix - AddLib 5` (DISABLED) — 作者 hidden mod，#16464 是 backup
2. `Luma 2.0 Beta - SFSE 1-14-70` (DISABLED) — 作者 Filoppi 正在修 1.5 patch
3. `CharGenMenu - SFSE 1-16-242` (DISABLED) — 新加，等作者出 1.16.244 兼容

#### 教训进 skill / KB / memory
**"latest published Nexus version" ≠ "compatible with current runtime"** — 必须在升级前去 Nexus changelog / 评论 / 作者声明里**实证**新版本对当前 runtime 的支持。会进 `install-planning.mod-update-post-state-discipline.v1` 增加 section。
