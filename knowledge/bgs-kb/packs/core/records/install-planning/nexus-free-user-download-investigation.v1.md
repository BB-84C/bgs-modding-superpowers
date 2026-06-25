---
id: install-planning.nexus-free-user-download-investigation.v1
title: Nexus free-user download — no agent-autonomous path exists post Chrome 127
kind: rule
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "Nexus has no anonymous-API read endpoints (all /v1/* return 401), and post Chrome 127 the browser cookie store is app-bound-encrypted (v20 prefix) such that simple PowerShell DPAPI extraction cannot decrypt session cookies. There is NO equivalent to Bilibili's sessdata cookie for Nexus. For free-account users (no Premium API key), the only agent-friendly workflow is HYBRID: user manually downloads via browser (passing Cloudflare WAF + waiting timer), drops file at agreed path, agent processes from there (extract / structure-flatten / backup / replace / meta.ini update / xSE cascade tracking)."
  confidence: high
queryKeys: [nexus free user, no API key, sessdata equivalent, Chrome v20 cookies, app-bound encryption, browser session, Cloudflare WAF, hybrid download workflow, manual download path, agent autonomy ceiling]
severity: high
sources:
  - kind: official
    url: "https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/os_crypt/sync/os_crypt_win.cc"
    ref: "Chromium os_crypt — DPAPI-wrapped AES key (works for v10/v11; v20 has additional app-bound wrap)"
  - kind: community-forum
    url: "https://blog.google/threat-analysis-group/google-chrome-127-app-bound-encryption-cookies/"
    ref: "Chrome 127 app-bound encryption (ABE) introduction for cookies (July 2024)"
  - kind: project-internal-doc
    url: "https://github.com/BB-84C/bgs-modding-superpowers/blob/main/docs/modpack-dev-logs/bb84-starfield/dev-log.md"
    ref: "BB84 2026-06-24 round-2 dev-log 'Nexus auth investigation' section"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Nexus free-user download — no agent-autonomous path exists post Chrome 127

For users who do NOT have a Nexus Premium account (and therefore no APIKEY for the `/v1/games/{game}/mods/{id}/files/{file_id}/download_link.json` Premium endpoint), the question becomes: can the agent autonomously download mods on behalf of the user without manual intervention? The empirical answer, after a 2026-06-24 investigation, is **no** — and trying to fake it is the kind of behavior that triggers infostealer-style anti-malware heuristics.

## What was tried and what failed

### Path 1: Anonymous Nexus API
- `GET https://api.nexusmods.com/v1/games.json` → 401 Unauthorized
- `GET https://api.nexusmods.com/v1/users/validate.json` → 401 Unauthorized
- Every Nexus API endpoint requires either `APIKEY` header (legacy key) or OAuth Bearer token. There is NO anonymous read tier.

### Path 2: Browser cookie reuse (the "sessdata" hope)
- Probed Chrome's `Cookies` SQLite for `.nexusmods.com` — found 51 cookies including `cf_clearance` (Cloudflare WAF clearance), `__cflb` (load balancer), `token_invalidated_at`, `ips4_*` (forum auth), and various analytics/ad cookies.
- **No cookie named `nexusmods_session`, `next-auth.session-token`, or any obvious bearer-token equivalent.** Nexus's modern auth keeps the session server-side and exposes only a CSRF-like + Cloudflare bot-clearance via cookies.
- ALL 51 cookies have v20 prefix (Chrome's app-bound encryption, introduced in Chrome 127, July 2024). Plain DPAPI extraction of the AES key from `Local State` correctly produces the 32-byte AES-256-GCM key, but decryption of v20 cookies FAILS because the v20 wrapping requires a second unwrap by chrome.exe's signed elevation service (a deliberate anti-infostealer design).
- Workarounds exist (Chrome `--remote-debugging-port`, third-party injection tools) but all either disrupt the user's workflow or behave like infostealer malware.

### Path 3: Cloudflare-WAF-gated HTML scrape
- `GET https://www.nexusmods.com/` returns 403 to any non-browser User-Agent (Cloudflare bot challenge).
- Even with a real browser User-Agent, the `cf_clearance` cookie is required to pass — and obtaining `cf_clearance` requires a JavaScript challenge solve that Invoke-WebRequest cannot perform.

## What works — the hybrid workflow

The agent-friendly free-account workflow is:

1. **Agent surfaces what needs downloading**: lists mods + Nexus URLs + target categories from BB84's `F:\Starfield Mods\<category>\` convention (or whatever the user's download organization is).
2. **User manually downloads** via Chrome / Firefox by clicking the "Manual Download" button on each Nexus mod page. Chrome handles Cloudflare WAF, captcha, and the wait timer. Free user accepts 10-30 second wait per file. File lands in user's chosen download path.
3. **Agent monitors download path** for new archives matching the expected names.
4. **Agent takes over from the file**:
   - Extract to staging (handle 7z subdirectory gotcha)
   - Inspect structure (handle `Data/` prefix flatten if present)
   - Backup current MO2 mod folder
   - Replace files in mod folder
   - Update `meta.ini` (`modid=`, `version=`, `newestVersion=`, `installationFile=`, `lastNexusUpdate=`, `lastNexusQuery=`)
   - For xSE plugin mods, also update folder name if it encodes a version tag (`- AddLib 22`, `- Game version 1.16.244`, etc.)

What the user gains by giving up Premium isn't the download speed (Premium CDN is faster but free accounts still get a usable download eventually). It's the **agent automation post-download**: the curator-grade processing of extract / flatten / backup / replace / meta-update / cascade-tracking. That's where the time savings live for a 300-mod modpack with regular updates.

## Don't fake it

**Anti-pattern**: using third-party Chrome cookie decrypt tools that inject into the elevation service. These tools work but they're functionally indistinguishable from infostealer malware and may trigger Windows Defender / EDR alerts. Even if benign for our purposes, the curator-tool plugin should not codify them.

**Anti-pattern**: using `--remote-debugging-port=9222` to drive Chrome via CDP and read cookies. Works technically but disruptive: the user must restart Chrome with the flag each session, lose their session state, and trust the agent with full browser-process control. Out of scope for a passive curator helper.

## See also

- `install-planning.mo2-windows-credential-mining.v1` — Premium API key path (when user has Premium + MO2 has stored the key in Win Credential Manager)
- `install-planning.nexus-direct-api-update-check.v1` — Option B refresh + Premium download_link mirror behavior
- `engine.xse-update-workflow.v1` — what the agent does AFTER the file is downloaded (cascade, flatten, backup, replace)
