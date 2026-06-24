# BB84自用2 Starfield Modpack — Mod Update Audit

> Generated: 2026-06-24 from local meta.ini cached state. **Caveat**: data reflects MO2's last Nexus query timestamp (typically 2025-08), not real-time Nexus state. For fresh data, run direct-Nexus-API refresh pass with personal API key.

## Summary

| Category | Count |
|---|---|
| Nexus mods total | 172 |
| Mods with cached version mismatch (`version != newestVersion`) | 30 |
| CC mods total | 132 (79 originals + 53 SC) |
| CC marketplace name found via web search | 125 / 132 (94.7%) |
| CC marketplace name NOT found (best-guess in notes) | 6 unique stems |
| SFSE current / latest | 0.2.20 (runtime 1.15.222) / 0.2.21 (runtime 1.16.244) |
| Address Library current / latest | v19 / v22 |

## Fresh Nexus refresh — 2026-06-24 (Option B workflow)

Refreshed all 172 Nexus mods via direct API (/v1/games/starfield/mods/{id}.json) on 2026-06-24.

### NEW UPDATE-tagged mods (after refresh)

| # | Mod folder | Nexus ID | Local version -> Current |
|---:|---|---:|---|
| 1 | Address Library | 3256 | 19.0.0.0 -> 22 |
| 2 | Aio Ultimate ChargenMenu Presets | 8686 | 1.2.0.0 -> v1.2 |
| 3 | Airlocks - Modders Resource | 12532 | d2025.8.23.0 -> .0.9.5 |
| 4 | Astral Lounge.FM | 3868 | 1.0.0.0 -> 1.0 |
| 5 | Astrogate 4.0 Beta | 9363 | d2025.7.11.0 -> 5.8 |
| 6 | ATLAS Clothing - Advanced Techwear 1.2 | 12704 | 1.2.0.0 -> 1.2 |
| 7 | Atmosphere Affects Radiation | 14298 | 1.0.0.0 -> 1.0 |
| 8 | Baka Achievement Enabler - AddLib 18 | 658 | 6.0.0.0 -> 7.0.0 |
| 9 | Baka Quick Full Saves - AddLib 18 | 1750 | 6.0.0.0 -> 7.0.0 |
| 10 | Barefoot Footstep Sounds for Shoeless Clothing | 7653 | 1.1.0.0 -> 1.1 |
| 11 | Bullet hole Impact 2.0 | 3026 | 2.0.0.0 -> 2.0 |
| 12 | Cassiopeia Papyrus Extender | 10896 | 5.0.0.0 -> 9.4 |
| 13 | Clean Chinese Fonts | 391 | 1.0.0.0 -> 1.0 |
| 14 | Clean Vanilla Hitmarker | 1689 | 1.5.0.0 -> 1.5 |
| 15 | Community Spaceship Expansion | 14174 | 1.3.1.0 -> 1.3.2 |
| 16 | Community Spaceship Expansion - Buyable Ships | 14174 | 1.0.0.0 -> 1.3.2 |
| 17 | Dark Universe - Crossfire | 8994 | 2.1.0.0 -> 2.0.1 |
| 18 | Dark Universe - Crossfire - SC | 10276 | 2.1.0.0 -> 2.1.0 |
| 19 | Dark Universe - Takeover | 11045 | 1.1.0.0 -> 2.1.0 |
| 20 | Dark Universe - Takeover - SC | 11628 | 1.1.0.0 -> 1.0.1 |
| 21 | Dark Universe Overtime | 13175 | 1.1.2.0 -> 1.1.2 |
| 22 | Darker Nights | 9616 | 1.1.0.0 -> 1.0 |
| 23 | Detailed Reference Info | 7589 | 7.1.0.0 -> 10.0 |
| 24 | Enhanced Lights and FX | 54 | 0.1.1.0 -> 0.1.1 |
| 25 | Enhanced Lights and FX CHS | 11794 | 0.1.1.0 -> 0.1.1 |
| 26 | Fallout Radio | 3839 | 1.0.0.0 -> 1.2 |
| 27 | Grendel suppressor replacement | 3094 | 1.0.0.0 -> 1.0 |
| 28 | Immersive Cargo Halls | 14217 | 1.0.0.0 -> 1.0.1 |
| 29 | Immersive Landing Ramps | 8093 | 3.0.0.0 -> 3.1.0 |
| 30 | Immersive Landing Ramps - Landing Animation Reloaded v1.6.3 Patch | 8093 | Patch-LAR-1.6.3 -> 3.1.0 |
| 31 | Immersive Landing Ramps - SC | 11653 | d2025.7.3.0 -> 1.0 |
| 32 | Immersive Ship Greetings | 14231 | 1.0.0.0 -> 1.0 |
| 33 | Immersive Star Colours | 14274 | 1.1.0.0 -> 1.0.0 |
| 34 | Immersive Starborn Temples | 10972 | 1.0.0.0 -> 1.0 |
| 35 | Laser Sights No Dots Fix | 10898 | 1.0.0.0 -> 1.0 |
| 36 | Left Align XP Bar | 95 | f1.05 -> 1.06 |
| 37 | Less Rocks - GRiNDTerra | 13094 | f1.02 -> 2.0 |
| 38 | Limitless Ship Builder | 12184 | 1.0.0.0 -> 1.0 |
| 39 | Linked Companion Spacesuit | 2632 | 1.4.0.0 -> 1.4 |
| 40 | Luma 2.0 Beta - SFSE 1-14-70 | 4821 | d2024.10.1.0 -> 778860b |
| 41 | Milkdrinker's New Atlantis Mesa Trees Reborn | 13137 | 1.0.0.0 -> 1.0 |
| 42 | More Immersive Landings And Takeoffs | 2835 | 1.4.0.0 -> 1.4.1 |
| 43 | More Visualized Docking | 4679 | 1.3.0.0 -> 1.3.2 |
| 44 | NAT Station Lake Windows | 14158 | 2.0.0.0 -> 2.1.0 |
| 45 | No More Tiers for Shattered Space | 9848 | 1.0.0.0 -> 1.4 |
| 46 | No More Tiers Plus 1.3 | 9848 | 1.2.0.0 -> 1.4 |
| 47 | No Sound In Space | 3156 | 0.2.0.0 -> 0.2 |
| 48 | Non-Lethal Framework | 7812 | 3.0.2.0 -> 3.2 |
| 49 | Non-Lethal Framework - SC | 8615 | 1.0.0.0 -> 1.0 |
| 50 | NPCNOSPREAD | 7050 | d2025.8.7.0 -> 1.0.0 |
| 51 | Paper Books | 3139 | 1.0.0.0 -> 1.0.0 |
| 52 | Perk Auto Level - SFSE 1-8-86 Waiting For Update | 5154 | 1.1.0.0 -> 1.2 |
| 53 | Permanent POIs | 13899 | f1.01 -> 1.01 |
| 54 | Permanent POIs - Darkness Beckons | 14188 | f1.02 -> 1.02 |
| 55 | Permanent POIs - Evil Beyond | 14059 | 0.94.0.0 -> 1.02 |
| 56 | Permanent POIs - Rogue Science | 14278 | 1.0.0.0 -> 1.05 |
| 57 | Places Of Intrigue - GRiNDTerra | 11530 | 3.5.0.0 -> 5 |
| 58 | POI Cooldown | 9532 | 2.0.0.0 -> 3 |
| 59 | Real Flashlight - Bigger Size Plugin | 570 | 1.2.0.0 -> 1.2 |
| 60 | Real Flashlight - Soft | 570 | 1.2.0.0 -> 1.2 |
| 61 | Real Fuel - BETA | 13306 | 1.1.2.0 -> 1.3.1 |
| 62 | Revelation - Main Quest Temple Overhaul | 10418 | 1.0.0.0 -> 1.5.0 |
| 63 | RRL OBJECTS - Rabbit's Real Lights Landing Pads | 11541 | 1.0.0.0 -> 1.0 |
| 64 | RRLAC - Rabbit's Real Lights Akila City | 10973 | 1.1.0.0 -> 1.2 |
| 65 | RRLC - Rabbit's Real Lights Cydonia | 11224 | 1.0.1.0 -> 1.0.1 |
| 66 | RRLG - Rabbit's Real Lights Gagarin | 11076 | 1.0.1.0 -> 1.0.1 |
| 67 | RRLHT - Rabbit's Real Lights HopeTown | 11381 | 1.0.0.0 -> 1.0 |
| 68 | RRLIT - Rabbit's Real Lights INI TWEAKS slightly brighter and better | 11050 | d2025.7.3.0 -> 1.1 |
| 69 | RRLN - Rabbit's Real Lights Neon | 11498 | 1.0.0.0 -> 1.0 |
| 70 | RRLNA - Rabbit's Real Lights New Atlantis | 10874 | 1.3.0.0 -> 1.4 |
| 71 | RRLNH - Rabbit's Real Lights New Homestead | 11590 | 1.0.0.0 -> 1.0 |
| 72 | RRLP - Rabbit's Real Lights Paradiso | 11701 | 1.0.0.0 -> 1.0 |
| 73 | Seamless City Interiors | 12344 | 1.1.0.0 -> 1.2.0 |
| 74 | Seamless Grav Jump 2.2 - Gravity Well Version | 9666 | 2.2.0.0 -> 2.2 |
| 75 | Seek Out Stores - Conner's Cut | 5995 | 1.4.0.0 -> 1.4 |
| 76 | SETI - Ship Exterior Light | 11480 | 0.3.1.0 -> 0.3.1 |
| 77 | Ship Vendor Framework | 10057 | 1.5.4.0 -> 1.10.0 |
| 78 | Show Read Books | 8042 | 1.0.0.0 -> 1.0 |
| 79 | Show XP on Loading Screens | 5616 | 1.2.0.0 -> 2.0 |
| 80 | Simple Faster Walk | 1411 | 2.0.0.0b -> 2 |
| 81 | Skill Challenges Removed | 9893 | d2025.7.10.0 -> 2.0 |
| 82 | SKK Fast Start New Game - SC | 12927 | 1.0.0.0 -> V1.0 |
| 83 | SKKFastStartNewGame | 5971 | 14.0.0.0 -> 15 |
| 84 | Smart Aiming - Third to First Person (Updated) | 11706 | 4.0.0.0 -> 5.0.0 |
| 85 | Smart Aiming - Third to First Person (Updated) ini | 11706 | 1.0.0.0 -> 5.0.0 |
| 86 | Souls of Cities 4.4 | 8517 | 4.4.0.0 -> 10.0 |
| 87 | Spacewalk With A Purpose 0.2.2 | 10377 | 0.2.2.0 -> 0.2.2 |
| 88 | Sprint Headtracking Bug Fix | 2370 | 1.1.1.0 -> 1.1.1 |
| 89 | Starfield anomaly style scope overhaul | 1949 | 0.1.0.0 -> 0.1 |
| 90 | Starfield Community Patch - Traditional Chinese | 11795 | 1.0.0.0 -> 1.0 |
| 91 | Starfield Engine Fixes - Game version 1.15.222 | 10457 | 13.0.0.0 -> 20.2 |
| 92 | Starfield Extended - Craftable Quality | 5721 | f4.02-FM -> v4.1.0 |
| 93 | Starfield Extended - Craftable Quality - SC | 8660 | f4.02-FM -> v4.1.0 |
| 94 | Starfield Extended - Craftable Quality - Shattered - SC | 8660 | f4.02-FM -> v4.1.0 |
| 95 | Starfield Extended - Craftable Quality Shattered | 5721 | f4.02-FM -> v4.1.0 |
| 96 | Starfield HD Overhaul - ESM | 5124 | f3.09 -> 3.14 |
| 97 | Starfield HD Overhaul part 01 | 5124 | f3.09 -> 3.14 |
| 98 | Starfield HD Overhaul part 02 | 5124 | f3.09 -> 3.14 |
| 99 | Starfield HD Overhaul part 03 | 5124 | f3.09 -> 3.14 |
| 100 | Starfield HD Overhaul part 04 | 5124 | f3.09 -> 3.14 |
| 101 | Starfield HD Overhaul part 05 | 5124 | f3.09 -> 3.14 |
| 102 | Starfield HD Overhaul part 06 | 5124 | f3.09 -> 3.14 |
| 103 | Starfield HD Overhaul part 07 | 5124 | f3.09 -> 3.14 |
| 104 | Starfield HD Overhaul part 08 | 5124 | f3.09 -> 3.14 |
| 105 | Starfield HD Overhaul part 09 | 5124 | f3.09 -> 3.14 |
| 106 | Starfield HD Overhaul part 10 | 5124 | f3.09 -> 3.14 |
| 107 | Starfield HD Overhaul part 11 | 5124 | f3.09 -> 3.14 |
| 108 | Starfield HD Overhaul part 12 | 5124 | f3.09 -> 3.14 |
| 109 | Starfield HD Overhaul part 13 | 5124 | f3.09 -> 3.14 |
| 110 | Starfield HD Overhaul part 14 | 5124 | f3.09 -> 3.14 |
| 111 | Starfield HD Overhaul part 15 | 5124 | f3.09 -> 3.14 |
| 112 | Starfield HD Overhaul part 16 | 5124 | f3.09 -> 3.14 |
| 113 | Starfield Locomotion Innovation Mod - SLIM | 4588 | 0.3.1.0 -> 0.3.1 |
| 114 | Starfield Optimizations INI | 104 | 1.1.0.0 -> 1.2 |
| 115 | Starfield Script Extender 1-15-222 | 106 | 0.2.18.0 -> 0.2.21 |
| 116 | Starfield Shader Injector - SFSE 1-12-30 | 5562 | 1.7.0.0 -> 1.9 |
| 117 | Starshake - Vizualized Recoil | 10131 | 2.0.0.0 -> 2.1.0 |
| 118 | StarUI Configurator | 5467 | 1.1.0.0 -> 1.1 |
| 119 | StarUI HUD | 3444 | 1.3.0.0 -> 1.3 |
| 120 | StarUI HUD - SC | 3474 | 1.3.0.0 -> 1.3 |
| 121 | StarUI Inventory | 773 | 2.4.1.0 -> 2.4.1 |
| 122 | StarUI Inventory - SC | 804 | 2.4.0.0 -> 2.4 |
| 123 | StarUI Outpost | 5766 | 1.3.0.0 -> 1.3 |
| 124 | StarUI Ship Builder | 6402 | 1.3.0.0 -> 1.3 |
| 125 | StarUI Ship Builder - SC | 11808 | 1.3.0.0 -> 1.3 |
| 126 | StarUI Workbench | 4966 | 1.2.0.0 -> 1.2 |
| 127 | StarUI Workbench - SC | 5153 | 1.1.0.0 -> 1.1 |
| 128 | Starvival - Immersive Survival Addon | 6890 | 10.8.0.0 -> 12.4.6 |
| 129 | Starvival - Immersive Survival Addon - New | 6890 | 11.0.0.0 -> 12.4.6 |
| 130 | Starvival - Immersive Survival Addon - SC | 14090 | f10.8 -> 10.8.0 |
| 131 | Stroud Premium Edition | 12330 | 2.3.3.0 -> 2.5.3 |
| 132 | Take Your Time | 10419 | 1.1.1.0 -> 1.5.0 |
| 133 | Take Your Time - Shattered Space | 10419 | 1.0.0.0 -> 1.5.0 |
| 134 | The Eyes of Beauty - Starfield - Replacer only | 493 | 1.0.0.0 -> 1.1.1 |
| 135 | The Gang's All Here | 7469 | 4.1.0.0 -> 4.2 |
| 136 | The Gang's All Here - Shattered Space | 7469 | 4.1.0.0 -> 4.2 |
| 137 | The Real Elevator 2.0.0 | 10904 | 2.0.0.0 -> 2.0.0 |
| 138 | Trainwreck SFSE | 5068 | 1.4.0.0 -> 1.4.0 |
| 139 | Trees Rescaled | 11731 | 1.0.0.0 -> V1.0 |
| 140 | TrueVision | 13987 | 1.0.1.0 -> 1.0.1 |
| 141 | TrueVision Shattered Space DLC | 13987 | 1.0.1.0 -> 1.0.1 |
| 142 | UC Military Overhaul - All-In-One | 11350 | 2.1.0.0 -> 2.2 |
| 143 | UC Military Overhaul - Complete Edition | 12085 | 1.2.0.0 -> 1.3 |
| 144 | UC Surplus Expanded - Immersive | 7205 | 1.2.0.0 -> 1.3 |
| 145 | UCMO - Marine Skin Pack | 11687 | 1.2.0.0 -> 1.2 |
| 146 | UCMO - Navy Fatigues Skin Pack (Gloves) | 12458 | 1.0.0.0 -> 1.0 |
| 147 | UCMO - Spec Ops Skin Pack | 11819 | 1.1.0.0 -> 1.2 |
| 148 | UCMO - Vanguard Pilot Skin Pack | 11702 | 2.1.0.0 -> 2.1 |
| 149 | Undelayed Menu - Latest Version | 404 | 1.0.6.0 -> 1.0.6 |
| 150 | UnlimitedMannequins | 6291 | 1.0.0.0 -> 1.0 |
| 151 | Usable bench press and pull up bar | 10301 | 1.0.0.0 -> 1.0 |
| 152 | Usable bench press and pull up bar CN | 10784 | 1.0.0.0 -> 1.0 |
| 153 | Useful Brigs | 8139 | 5.0.1.0 -> 6.0.5 |
| 154 | Useful Brigs - SC | 8614 | 1.0.0.0 -> 1.0 |
| 155 | VASCO-9000 Voice Replacement | 3306 | 1.0.0.0 -> 1.0 |
| 156 | Vend Unto Floor | 8191 | 1.1.2.0 -> 1.1.2 |
| 157 | Visible Chronomark Watch | 8092 | 2.0.0.0 -> 2.0.0 |
| 158 | VPRD Elevator | 11440 | 1.10.0.0 -> 1.10 |
| 159 | Weapons of Fate (Ballistics Overhaul) | 162 | 1.1.1.0 -> 1.1.1 |
| 160 | Xeno Master | 10380 | 1.1.5.0 -> 1.2.77 |
| 161 | Xeno Master Addon Trade Authority can sell XM Items | 10380 | 1.1.4.0 -> 1.2.77 |
| 162 | Xeno Master Carpwalker naming and Aceles keyword fix | 10380 | 1.1.4.0 -> 1.2.77 |

### Mods removed/hidden on Nexus

| # | Mod folder | Nexus ID | Status | nexusFileStatus |
|---:|---|---:|---|---:|
| 1 | CharGenMenu | 20 | not_published | 1 |
| 2 | Denser Vegetation - GRiNDTerra | 9710 | removed | 6 |
| 3 | ImmersiveDataSlates | 6004 | hidden | 9 |
| 4 | Just Random Vegetation Rock and Exotic Sizes - GRiNDTerra | 11334 | removed | 6 |
| 5 | OwlTech_Pathfinder | 14019 | hidden | 9 |
| 6 | Space Ship Landing Reloaded | 7569 | removed | 6 |
| 7 | VaruunTI Habs | 12083 | removed | 6 |
| 8 | Weapon Swap Stuttering Fix - AddLib 5 | 2830 | hidden | 9 |

### Comparison vs stale-cache audit

- Previously UPDATE-tagged (stale): 30
- Currently UPDATE-tagged (fresh): 162
- Confirmed still need update: 30
- Stale cache had false positive: 1
- NEW updates discovered (was current in cache, now stale): 132
- API errors: 0
- Nexus hourly rate budget remaining after final header check: 1825
- Nexus daily rate budget remaining after final header check: 19825
- Fresh refresh log: $jsonPath

## Nexus mods with cached version mismatch (30 entries)

### Lane 1 (8)
- Astrogate 4.0 Beta
- Fallout Radio
- Immersive Landing Ramps - Landing Animation Reloaded v1.6.3 Patch
- Luma 2.0 Beta - SFSE 1-14-70
- Permanent POIs - Evil Beyond
- Revelation - Main Quest Temple Overhaul
- Souls of Cities 4.4
- Take Your Time - Shattered Space

### Lane 2 (7)
- Dark Universe - Takeover - SC (`→ 1.0.1.0`)
- Immersive Landing Ramps - SC (`→ 1.0.0.0`)
- ImmersiveDataSlates (`→ f1.00`)
- Permanent POIs - Rogue Science (`→ 0.97.0.0`)
- Show XP on Loading Screens (`→ 2.0.0.0`)
- Starfield Optimizations INI (`→ 1.2.0.0`)
- Starvival - Immersive Survival Addon - SC (`→ 10.8.0.0`)

### Lane 3 (7)
- Dark Universe - Crossfire
- Dark Universe Overtime
- Immersive Cargo Halls
- No More Tiers Plus 1.3
- NPCNOSPREAD
- RRLIT
- Xeno Master Addon Trade Authority can sell XM Items

### Lane 4 (8)
- Darker Nights
- Immersive Star Colours
- Real Fuel - BETA
- Skill Challenges Removed
- Starfield Shader Injector - SFSE 1-12-30
- Starvival - Immersive Survival Addon
- Take Your Time
- Xeno Master Carpwalker naming and Aceles keyword fix

> Full version numbers in each mod's `meta.ini` `notes=` field. Use `D:\awesome-bgs-mod-master\.opencode\artifacts\bb84-starfield-audit-2026-06-24\nexus-lanes\lane-*-extract.json` for `version → newestVersion` mapping.

## CC mods where web-search did not find marketplace name

These have notes prefixed `[CC] (未找到)` or `(根据 esm 文件名推测: ...)`. May need manual in-game verification or Bethesda Creations browse:

- **No Loading Ship** (lane 1)
- **astrogate** (lane 2 + 3 — both lanes hit it)
- **bubegg** (lane 2)
- **satou_sr2_destroy01** (lane 2)
- **tankgirlsxenologyexpanded** (lane 2)
- **rvexplore** (lane 3)

## Refresh strategy

**Stale-data caveat**: cached `newestVersion` reflects MO2's last `Tools → Check All for Updates` query (~2025-08 for most mods in this audit). To get current state:

### Option B (recommended per `mo2-update-check-investigation.md`) — Direct Nexus API refresh

- Endpoint: `GET https://api.nexusmods.com/v1/games/starfield/mods/updated.json?period=1m`
- Auth: `APIKEY: <user-api-key>` header (no Premium required)
- Rate budget: 20k/day; full sweep = ~173 calls
- Write back via `mo2_edit_meta` MCP tool (refreshes `version`, `newestVersion`, `nexusFileStatus`, `lastNexusQuery`, `lastNexusUpdate` in meta.ini)

### MO2 GUI fallback

Launch MO2 → Tools → Check All for Updates (requires Nexus authentication in MO2 settings).

## Known engine-level updates (out-of-band, do not refresh via Nexus mod-page API)

- **SFSE 0.2.20 → 0.2.21** — requires Starfield runtime 1.16.244 (current local: 1.15.222). Drops into game root, NOT MO2 mod folder. See dev-log Task 4.
- **Address Library v19 → v22** — Nexus mod #3256, normal MO2 install (picked up by direct-API refresh above).

## CC update status caveat

CC files don't have Nexus version metadata. The `mtime` of `<stem>.esm` reflects install time, not source update time. Real CC update detection requires opening Starfield in-game → Creations menu → look for update prompts. Out of agent scope; user action only.

## See also

- `D:\Starfield MO2\docs\dev-log.md` — this audit round's full execution log
- `D:\Starfield MO2\docs\release-changelog.md` — pending changes list
- `D:\awesome-bgs-mod-master\.opencode\artifacts\bb84-starfield-audit-2026-06-24\mo2-update-check-investigation.md` — full Option B substrate
