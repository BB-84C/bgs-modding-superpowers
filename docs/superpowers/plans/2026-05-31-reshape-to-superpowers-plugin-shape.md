# Reshape `awesome-bgs-mod-master` → Superpowers-shaped Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reshape this repo from its current "dev harness + scattered scaffold" form into a Superpowers-style multi-harness plugin named `bgs-modding-superpowers`, installable on OpenCode, Claude Code, and Codex, that ships the existing xEdit MCP + MO2 control-plane payload to end-user modpack builders.

**Plugin name:** `bgs-modding-superpowers` (also the target GitHub repo name).

**Target harnesses (v0.1):** OpenCode, Claude Code, Codex. (Cursor and Gemini deferred.)

**Spec source:** the bundled design proposal in chat session 2026-05-31 (see "Reshape Proposal" section). No separate spec doc is created — design is captured at the top of this plan.

**Anchor references:**
- Superpowers shape: `obra/superpowers@v5.1.0` (per-harness manifests, `skills/<name>/SKILL.md` at root, version sync via `.version-bump.json`, OpenCode plugin JS does `config.skills.paths` + first-user-message bootstrap injection).
- OpenCode MCP wiring precedent: `alvinunreal/oh-my-opencode-slim` (`config:` hook merges `opencodeConfig.mcp` + plugin-return `mcp:` field; ships pre-built `dist/` via npm + `prepare: build` script).
- Claude Code MCP wiring: `.mcp.json` at plugin root with `${CLAUDE_PLUGIN_ROOT}` placeholder. Reference: `anthropics/claude-plugins-official/external_plugins/imessage/.mcp.json`, `popup-studio-ai/bkit-claude-code/.mcp.json`.
- Codex plugin shape: `openai/plugins` README — `.codex-plugin/plugin.json` + `.mcp.json` companion. Substitution placeholder for Codex untested — verify in acceptance.

---

## Locked design decisions

| # | Decision | Resolution |
|---|---|---|
| Naming | Plugin / GitHub repo name | `bgs-modding-superpowers` |
| Skills (per-session) | Bootstrap loaded on every session | `skills/using-bgs-modding-superpowers/` |
| Skills (first-run) | Bootstrap run once after install | `skills/setting-up-bgs-modding-environment/` (loaded on demand; orchestrates MO2 detection + xEdit install + dev-log init via other skills) |
| Templates | `templates/modpack/` directory | **Deleted.** Dev-log + release-changelog created at runtime by dedicated skills. |
| `agents/repo-bootstrap/` | Internal bootstrap-agent persona | **Deleted.** |
| Contributor doc | Public guide for PR contributors | `CONTRIBUTING.md` (no public `CLAUDE.md`). |
| Phase-0 stub skills | Old `skills/{conflict-auditor,install-planner,...}` | Move to `docs/internal/future-skills/` as design notes. |
| MCP/hook spec MDs | `mcps/*.md`, `hooks/*.md` | Move to `docs/internal/{mcp-specs,hook-specs}/`. |
| Empty placeholders | `commands/`, `knowledge/`, `research/summaries/` | Delete. |
| Dev memory | `AGENTS.md` (root), `.opencode/{memory,artifacts,skills}` | Stays gitignored. **Working skills move out to top-level `skills/`**; `.opencode/` itself stays fully ignored. |
| LB-1 MCP declaration | Per-harness manifest declaration | OpenCode plugin JS `config.mcp.xedit`; Claude Code `.mcp.json` at root with `${CLAUDE_PLUGIN_ROOT}`; Codex `.mcp.json` (same shape, smoke-test substitution). |
| LB-2 MO2 install | How end users install C++ control-plane DLL + Python loader | **Combined into `setting-up-bgs-modding-environment` skill.** Detect MO2; if absent → guide human install. Allow opt-in: (a) agent-handled install, (b) "no MO2 needed" mode. |
| LB-3 xEdit install | How end users get xEdit + hook-bridge DLL | **Combined into `setting-up-bgs-modding-environment` skill.** xEdit binary: download latest release from `BB-84C/TES5Edit` into `<MO2_Root>\tools\xEdit\` on user consent. **`xEditHookBridge.dll` is OWNED BY THIS REPO** — ships from `tools/xedit-hook-bridge/dist/xEditHookBridge.dll`, deployed by installer scripts. `.pas` source is dev-only (lives in sister `D:\TES5Edit-contrib`); gitignored here if ever appears. |
| LB-4 Harness scope | v0.1 target harnesses | OpenCode + Claude Code + Codex. |
| LB-5 Gitignore | `.gitignore` policy | Keep `/.opencode` and `AGENTS.md` ignored as today. Move working skills out, do not track `.opencode/`. |
| `dist/` shipping | TS build output | Commit pre-built `dist/` to git **and** add `prepare: npm run build` to `tools/xedit-mcp/package.json` (belt-and-suspenders: works for direct checkout and for git-package install). |

---

## File Structure (post-reshape)

```
awesome-bgs-mod-master/                            (= bgs-modding-superpowers repo)
├── skills/                                        # SHIPPABLE PAYLOAD
│   ├── using-bgs-modding-superpowers/             # per-session bootstrap
│   │   └── SKILL.md
│   ├── setting-up-bgs-modding-environment/        # first-run install / MO2 + xEdit setup
│   │   └── SKILL.md
│   ├── xedit-automation/                          # hub skill (moved from .opencode/skills/)
│   │   ├── SKILL.md
│   │   └── xedit-knowledgebase.md                 # scrub D:\TES5Edit-contrib\ refs
│   └── xedit-conflict-audit/                      # task skill (moved)
│       └── SKILL.md
├── tools/
│   ├── xedit-mcp/                                 # TS MCP, committed dist/, prepare-builds on install
│   │   ├── package.json                           # add `prepare: npm run build`
│   │   ├── dist/                                  # tracked
│   │   ├── src/
│   │   ├── tests/                                 # not shipped (npm files allowlist)
│   │   └── README.md
│   ├── mo2-vfs-launcher/                          # PS outer client (unchanged location)
│   ├── mo2-control-plane/                         # C++ DLL src + broker + Python loader
│   │   └── live-bridge/deploy-live-bridge.ps1     # P5: replace .artifacts/mo2/ default with required flag
│   └── xedit-hook-bridge/                       # OURS; ship dist/, ignore src/.pas + build leftovers
│       └── dist/xEditHookBridge.dll             # tracked
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── .codex-plugin/
│   └── plugin.json
├── .mcp.json                                      # shared between CC + Codex; uses ${CLAUDE_PLUGIN_ROOT}
├── .opencode/                                     # GITIGNORED (entire tree)
│   ├── plugins/bgs-modding-superpowers.js         # tracked exception via !/.opencode/plugins/ rule
│   ├── INSTALL.md                                 # tracked
│   ├── memory/                                    # dev memory, untracked
│   ├── artifacts/                                 # dev artifacts, untracked
│   └── skills/                                    # legacy untracked stash (post-move it stays empty)
├── hooks/
│   ├── hooks.json                                 # CC session-start
│   ├── session-start                              # POSIX shell
│   └── run-hook.cmd                               # Windows shim
├── scripts/
│   ├── bump-version.sh                            # version sync across manifests
│   ├── install-mo2-control-plane.ps1              # P6: deploy DLL + py to user MO2
│   └── fetch-xedit-release.ps1                    # P6: download BB-84C/TES5Edit latest into <MO2>/tools/xEdit
├── .version-bump.json
├── package.json                                   # root, main → .opencode/plugins/bgs-modding-superpowers.js
├── README.md                                      # rewrite: per-harness install table
├── CONTRIBUTING.md                                # PR guidance (replaces idea of public CLAUDE.md)
├── RELEASE-NOTES.md
├── LICENSE                                        # add if missing
├── AGENTS.md                                      # GITIGNORED dev router (unchanged)
├── tests/                                         # dev-only PS test suites (stays at root)
├── docs/
│   ├── internal/                                  # consolidated dev-only docs
│   │   ├── roadmap.md
│   │   ├── plans/                                 # 31 old dev plans
│   │   ├── superpowers/{specs,plans}/             # incl this plan
│   │   ├── standards/repo-hygiene.md
│   │   ├── research/
│   │   ├── future-skills/                         # ex-Phase-0 stubs
│   │   ├── mcp-specs/                             # ex-mcps/
│   │   ├── hook-specs/                            # ex-hooks/
│   │   └── repo-bootstrap.md                      # absorbed agents/repo-bootstrap content (or deleted)
│   └── (public docs added later if needed)
├── .artifacts/                                    # gitignored dev MO2 harness (unchanged)
├── .external-resource/                            # gitignored (unchanged)
├── .worktrees/                                    # gitignored (unchanged)
└── .gitignore                                     # unchanged policy; add !/.opencode/plugins/ and !/.opencode/INSTALL.md exceptions
```

### `.gitignore` policy

User decision: keep `/.opencode` and `AGENTS.md` gitignored. The OpenCode plugin code and `INSTALL.md` must be tracked exceptions. Correct git semantics: parent-dir exclusion blocks re-inclusion, so the pattern must use `/*` (single-level) rather than `/` (whole-tree). Final pattern:

```gitignore
/.opencode/*
!/.opencode/plugins/
!/.opencode/INSTALL.md
AGENTS.md
```

This keeps `.opencode/memory/`, `.opencode/artifacts/`, and `.opencode/skills/` untracked, while allowing `.opencode/plugins/**` and `.opencode/INSTALL.md` to be tracked. (Files under `.opencode/plugins/` are not auto-ignored because `/.opencode/*` only matches one path level.)

---

## Branch + worktree convention

- Feature branch: `reshape/superpowers-plugin-shape`
- Base: current `main` (commit `764fdd4`).
- Uncommitted working-tree changes carried forward as-is.
- Prefer multiple small commits per phase. No `.worktree/` — branch lives in main checkout.

---

## Phase P1 — Manifests + bootstrap wiring (additive, no file moves)

Goal: every harness can in principle find the plugin; no payload moved yet. Repo continues to work as today.

- [ ] P1.1 Create `package.json` at repo root with `name: "bgs-modding-superpowers"`, `version: "0.1.0"`, `type: "module"`, `main: ".opencode/plugins/bgs-modding-superpowers.js"`.
- [ ] P1.2 Create `.claude-plugin/plugin.json` (name, description, version, author, repo, license, keywords; no `skills:` field — auto-discovery by convention).
- [ ] P1.3 Create `.claude-plugin/marketplace.json` registering self as single-plugin marketplace.
- [ ] P1.4 Create `.codex-plugin/plugin.json` with `skills: "./skills/"` pointer + minimal `interface` block (displayName "BGS Modding Superpowers", brandColor, default prompts).
- [ ] P1.5 Create `.opencode/plugins/bgs-modding-superpowers.js`:
  - Implement `config:` hook that does `cfg.skills.paths.push(<absolute path to ./skills>)` and `cfg.mcp.xedit ??= { type: 'local', command: ['node', <absolute path to tools/xedit-mcp/dist/index.js>] }`.
  - Implement `experimental.chat.messages.transform` hook injecting the bootstrap skill body as the first user-message prefix (mirrors `superpowers.js` pattern; idempotency check on `EXTREMELY_IMPORTANT` marker).
  - Use `fileURLToPath(import.meta.url)` + `path.resolve(__dirname, '../../...')` for path resolution.
- [ ] P1.6 Create `.opencode/INSTALL.md` with end-user install steps (verbatim from `obra/superpowers/.opencode/INSTALL.md` adapted for `bgs-modding-superpowers`).
- [ ] P1.7 Create `.mcp.json` at repo root (shared between Claude Code and Codex):
  ```json
  {
    "mcpServers": {
      "xedit": {
        "command": "node",
        "args": ["${CLAUDE_PLUGIN_ROOT}/tools/xedit-mcp/dist/index.js"]
      }
    }
  }
  ```
- [ ] P1.8 Create `hooks/hooks.json` (Claude Code session-start), `hooks/session-start` (POSIX), `hooks/run-hook.cmd` (Windows shim). Hook command: print the bootstrap skill body to stdout (Claude Code injects it). Mirror `obra/superpowers/hooks/*` shape.
- [ ] P1.9 Create `.version-bump.json` declaring version fields across `package.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (`plugins.0.version`), `.codex-plugin/plugin.json`.
- [ ] P1.10 Create `scripts/bump-version.sh` (port from `obra/superpowers/scripts/bump-version.sh`).
- [ ] P1.11 Update `.gitignore`: add `!/.opencode/plugins/`, `!/.opencode/plugins/**`, `!/.opencode/INSTALL.md` exceptions under the existing `/.opencode` ignore.
- [ ] P1.12 Commit P1: `chore(reshape): add plugin manifests and bootstrap wiring (P1)`.

**P1 acceptance:** `npx opencode-cli` (or equivalent) sees the plugin name in its discovery output; no skills payload yet but the wiring is in place.

---

## Phase P2 — Skills consolidation (move working skills to tracked top-level)

Goal: skills payload lives at `skills/` (Superpowers convention) and is tracked in git.

- [ ] P2.1 Create `skills/` top-level directory.
- [ ] P2.2 Move `.opencode/skills/xedit-automation/{SKILL.md,xedit-knowledgebase.md}` → `skills/xedit-automation/`. **Scrub `D:\TES5Edit-contrib\` references in `xedit-knowledgebase.md`** — replace with `<repo>/tools/xedit-hook-bridge/` or `BB-84C/TES5Edit` GitHub URLs as appropriate.
- [ ] P2.3 Move `.opencode/skills/xedit-conflict-audit/SKILL.md` → `skills/xedit-conflict-audit/SKILL.md`.
- [ ] P2.4 Author `skills/using-bgs-modding-superpowers/SKILL.md` (per-session bootstrap). Content shape: mirrors `using-superpowers` — frontmatter `name`+`description`, `<EXTREMELY-IMPORTANT>` guardrails, instruction to invoke skills before acting, list of available task skills (`xedit-automation`, `xedit-conflict-audit`, `setting-up-bgs-modding-environment`), guidance on when to delegate to which.
- [ ] P2.5 Author `skills/setting-up-bgs-modding-environment/SKILL.md` (first-run bootstrap). Content shape:
  - Frontmatter: `name`, `description: "Use on first install OR when MO2/xEdit setup is incomplete/missing — detects user's environment, guides MO2 install if needed, installs the C++ control-plane DLL + Python loader into MO2, optionally installs xEdit from BB-84C/TES5Edit release."`
  - Checklist:
    1. Detect MO2 install (search `%LOCALAPPDATA%\ModOrganizer*`, `D:\ModOrganizer*`, ask user for path).
    2. If MO2 absent: surface `[BLOCKED]` to user; offer (a) human install + guide URL, (b) agent-handled install (consent required), (c) no-MO2 mode for non-modding work.
    3. Once MO2 found: run `scripts/install-mo2-control-plane.ps1 -MO2Root <path>` to deploy DLL + Python.
    4. Ask user if they want xEdit. If yes: run `scripts/fetch-xedit-release.ps1 -MO2Root <path>` to pull latest `BB-84C/TES5Edit` release into `<MO2>/tools/xEdit/`.
    5. Initialize a dev-log + release-changelog for the user's modpack project via the `writing-modpack-devlog` / `writing-modpack-changelog` skills (authored in P2.5b/c below).
    6. Verify install: smoke-call `xedit_list_capabilities` MCP tool; expect success.
- [ ] P2.5b Author `skills/writing-modpack-devlog/SKILL.md`. Frontmatter `name: writing-modpack-devlog`, description `"Use when starting or updating a dev-log for a modpack project. Creates <project>/docs/dev-log.md if missing; appends a new dated entry on subsequent calls."`. Body checklist: detect modpack project root (cwd or `<MO2_Root>/profiles/<Profile>/`?), locate or create `<project>/docs/dev-log.md`, append a dated entry with summary + author, prompt user for entry context. Provide canonical entry shape inline.
- [ ] P2.5c Author `skills/writing-modpack-changelog/SKILL.md`. Frontmatter `name: writing-modpack-changelog`, description `"Use when cutting a modpack release. Creates <project>/docs/release-changelog.md if missing; appends a new version section with grouped changes."`. Body checklist: detect project root, locate or create `<project>/docs/release-changelog.md`, prompt user for version + change summary, append section.
- [ ] P2.6 Delete old `.opencode/skills/*` directories (now empty after move). `.opencode/skills/` stays as an empty dir — fine because `.opencode/` is gitignored.
- [ ] P2.7 Commit P2: `feat(reshape): consolidate skills under tracked skills/ + author bootstrap + writing-modpack skills (P2)`.

**P2 acceptance:** `skills/` contains 6 dirs (`using-bgs-modding-superpowers`, `setting-up-bgs-modding-environment`, `writing-modpack-devlog`, `writing-modpack-changelog`, `xedit-automation`, `xedit-conflict-audit`). All have `SKILL.md` with proper YAML frontmatter (`name:` + `description:`). `git ls-files skills/` returns the new tracked files. `D:\TES5Edit-contrib\` no longer appears in any tracked file.

---

## Phase P3 — Doc reorganization + public-facing top-level docs

Goal: dev-only docs consolidated under `docs/internal/`; public README + CONTRIBUTING.md present.

- [ ] P3.1 Create `docs/internal/`.
- [ ] P3.2 Move `docs/roadmap.md` → `docs/internal/roadmap.md`.
- [ ] P3.3 Move `docs/plans/` → `docs/internal/plans/`.
- [ ] P3.4 Move `docs/standards/` → `docs/internal/standards/`.
- [ ] P3.5 Move `docs/research/` → `docs/internal/research/`.
- [ ] P3.6 Move `docs/superpowers/` → `docs/internal/superpowers/` (incl. this plan; update self-references).
- [ ] P3.7 Move `docs/initial_pormpt.md` → leave untracked / move under gitignored `.opencode/artifacts/` if user wants to preserve it (currently gitignored).
- [ ] P3.8 Move `skills/{conflict-auditor,install-planner,localization-assistant,mod-evaluator,test-session-guide,write-dev-log,write-release-changelog}/` → `docs/internal/future-skills/`. **Do not** ship these as runnable skills; they are design notes for v0.2+.
- [ ] P3.9 Move `mcps/{xedit-readonly,nexus-metadata,loot-metadata,translation-memory}.md` + `mcps/README.md` → `docs/internal/mcp-specs/`.
- [ ] P3.10 Move `hooks/{dev-log-reminder,repo-cleanliness,runtime-compatibility,scope-guard}.md` → `docs/internal/hook-specs/`. **Note:** `hooks/` at root is now reserved for runtime hook code (P1 work); the spec MDs are docs only.
- [ ] P3.11 Move `agents/repo-bootstrap/AGENT.md` content into `docs/internal/repo-bootstrap.md`, then delete `agents/` dir. (Per user: `agents/repo-bootstrap/` → deleted.)
- [ ] P3.12 Delete `commands/`, `knowledge/`, `research/`, `templates/` directories (per user: templates deleted, others empty placeholders).
- [ ] P3.13 Rewrite root `README.md` for end users: project elevator pitch, per-harness install table (OpenCode / Claude Code / Codex), "What works in v0.1" list, link to CONTRIBUTING.md for contributors.
- [ ] P3.14 Author `CONTRIBUTING.md`: how to clone, branch conventions, test commands, where dev docs live (`docs/internal/`), PR target branch.
- [ ] P3.15 Author `RELEASE-NOTES.md` skeleton (`## v0.1.0 (unreleased)` section).
- [ ] P3.16 Add `LICENSE` if missing. Default: MIT (confirm).
- [ ] P3.17 Commit P3: `docs(reshape): consolidate dev docs to docs/internal/, add public README+CONTRIBUTING (P3)`.

**P3 acceptance:** `ls` at repo root shows only public/runtime-relevant entries + `docs/`. Old placeholder dirs gone. README renders meaningfully for a new user.

---

## Phase P4 — MCP wiring verification (the manifests + dist already in place from P1)

Goal: per-harness MCP declarations actually reach `tools/xedit-mcp/dist/index.js` and the MCP server starts.

- [ ] P4.1 In `tools/xedit-mcp/package.json`, add `scripts.prepare`: `"prepare": "npm run build"` and ensure `scripts.build` compiles `src/` → `dist/`. Add `"files": ["dist", "src", "README.md", "package.json"]` if not present.
- [ ] P4.2 Build `tools/xedit-mcp/dist/` locally and verify `node tools/xedit-mcp/dist/index.js --help` (or stdio handshake) responds. Commit the built `dist/` to git on this branch.
- [ ] P4.3 Smoke-test OpenCode wiring: run `opencode` from `.artifacts/mo2/` with `opencode.json` pointing at the local plugin checkout (`"plugin": ["file:D:/awesome-bgs-mod-master"]` or git ref). Confirm `xedit_list_capabilities` tool appears.
- [ ] P4.4 Smoke-test Claude Code wiring: load the plugin via `/plugin install file:///D:/awesome-bgs-mod-master` (or marketplace ref). Confirm MCP `xedit` server registers via `.mcp.json`.
- [ ] P4.5 Smoke-test Codex wiring: install plugin via Codex CLI. Confirm `.mcp.json` is honored; if `${CLAUDE_PLUGIN_ROOT}` substitution fails on Codex, fall back to relative `./tools/xedit-mcp/dist/index.js` and document the limitation.
- [ ] P4.6 Commit P4: `feat(reshape): verify MCP wiring on OC/CC/Codex (P4)`.

**P4 acceptance:** at least one tool call (`xedit_list_capabilities`) succeeds end-to-end on each of OpenCode, Claude Code, Codex against the dev MO2 sandbox at `.artifacts/mo2/`.

---

## Phase P5 — Scrub migration blockers

Goal: shippable code no longer assumes `D:\awesome-bgs-mod-master\` or `D:\TES5Edit-contrib\` paths.

- [ ] P5.1 `tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1`: change `.artifacts/mo2/...` default to a required `-MO2Root` flag with no default. Error out with a clear message if absent.
- [ ] P5.2 `tools/mo2-control-plane/live-bridge/mo2_agent_control.py` lines 26-27: remove `.artifacts/mo2/` constants; read from env vars or constructor args.
- [ ] P5.3 `tools/xedit-mcp/tests/integration/diag-*.test.ts`: gate behind env var `BGS_MCP_DIAG=1`. By default skip these tests. Hardcoded `D:/awesome-bgs-mod-master/...` paths become opt-in.
- [ ] P5.4 `tools/xedit-mcp/tests/integration/live-conflict-audit.test.ts`: parameterize `xeditPath` via env `BGS_TEST_XEDIT_PATH`, default to relative `.artifacts/mo2/...` for local dev only.
- [ ] P5.5 `tools/xedit-mcp/README.md`: rewrite as user-facing MCP doc (what tools, how to invoke from agent harness). Move dev-only links into `docs/internal/`.
- [ ] P5.6 `tools/mo2-control-plane/live-integration.md`: move to `docs/internal/mo2-control-plane-live-integration.md`.
- [ ] P5.7 `grep -r '\.artifacts/mo2' tools/ skills/ .claude-plugin/ .codex-plugin/ .opencode/plugins/` returns no shippable hits. Same check for `D:\TES5Edit-contrib`, `D:\awesome-bgs-mod-master`.
- [ ] P5.8 Commit P5: `fix(reshape): scrub dev-sandbox paths from shippable surfaces (P5)`.

**P5 acceptance:** no shippable file contains a literal `.artifacts/mo2/`, `D:\awesome-bgs-mod-master\`, or `D:\TES5Edit-contrib\` reference. Tests still pass with `BGS_MCP_DIAG` unset (diag tests skip).

---

## Phase P6 — MO2 control-plane install path + xEdit fetch

Goal: `setting-up-bgs-modding-environment` skill has real backing scripts that work against an arbitrary MO2 install, not just the dev sandbox.

- [ ] P6.1 Author `scripts/install-mo2-control-plane.ps1`:
  - Args: `-MO2Root <path>` (required), `-Force` (overwrite existing install).
  - Behavior: validate `<MO2Root>/ModOrganizer.exe` exists; copy `tools/mo2-control-plane/plugin/build/Mo2AgentControl.dll` (or pre-built artifact path) to `<MO2Root>/plugins/`; copy `tools/mo2-control-plane/live-bridge/mo2_agent_control.py` to `<MO2Root>/plugins/`; copy broker bin/lib as appropriate.
  - Verification: list deployed files, print success.
- [ ] P6.2 Author `scripts/fetch-xedit-release.ps1`:
  - Args: `-MO2Root <path>` (required), `-ReleaseTag <tag>` (optional, default = latest).
  - Behavior: query `https://api.github.com/repos/BB-84C/TES5Edit/releases/latest`, download the canonical zip asset, extract into `<MO2Root>/tools/xEdit/`. Verify `xEdit.exe` exists post-extract.
- [ ] P6.3 Update `setting-up-bgs-modding-environment/SKILL.md` to reference these scripts by name.
- [ ] P6.4 Test both scripts against a clean MO2 install (the user's `.artifacts/mo2/` sandbox can be used, but the scripts must accept an arbitrary `-MO2Root` and not hardcode any path).
- [ ] P6.5 Commit P6: `feat(reshape): MO2 control-plane installer + xEdit fetch scripts (P6)`.

**P6 acceptance:** running both scripts with `-MO2Root D:\awesome-bgs-mod-master\.artifacts\mo2` cleanly deploys the control plane and (if invoked) fetches xEdit into `<MO2>/tools/xEdit/`. No paths are hardcoded.

---

## Phase P7 — `xEditHookBridge.dll` packaging (owned-by-this-repo)

Goal: ship the hook-bridge DLL from THIS repo as a tracked artifact (we own it). `.pas` source lives in sister `D:\TES5Edit-contrib` and stays out of this repo.

- [ ] P7.1 Move `tools/xedit-hook-bridge/src/xEditHookBridge.dll` → `tools/xedit-hook-bridge/dist/xEditHookBridge.dll`. Track in git (`git add -f` if needed).
- [ ] P7.2 Update `.gitignore` with scoped Delphi-leftover rules:
  ```gitignore
  /tools/xedit-hook-bridge/src/
  /tools/xedit-hook-bridge/*.dcu
  /tools/xedit-hook-bridge/*.dproj.local
  /tools/xedit-hook-bridge/*.identcache
  /tools/xedit-hook-bridge/*.res
  ```
- [ ] P7.3 Update `scripts/install-mo2-control-plane.ps1` (or a dedicated `scripts/install-xedit-hook-bridge.ps1`) to copy `tools/xedit-hook-bridge/dist/xEditHookBridge.dll` into the runtime location `xedit-mcp` expects — confirm against `tools/xedit-mcp/src/daemon-adapter.ts` and `tools/xedit-mcp/src/launch.ts` (likely co-located with `xEdit.exe` under `<MO2>/tools/xEdit/`).
- [ ] P7.4 Update `skills/xedit-automation/xedit-knowledgebase.md` and `skills/setting-up-bgs-modding-environment/SKILL.md`: clarify that `xEditHookBridge.dll` ships with this plugin (owned by us), distinct from xEdit itself which is downloaded from `BB-84C/TES5Edit`.
- [ ] P7.5 Document the dev-only build path in `docs/internal/xedit-hook-bridge-build.md`: `.pas` source lives at `D:\TES5Edit-contrib\<path>`, built by Delphi, output copied to `tools/xedit-hook-bridge/dist/`.
- [ ] P7.6 Commit P7: `feat(reshape): ship xEditHookBridge.dll from tools/xedit-hook-bridge/dist/ (P7)`.

**P7 acceptance:** `tools/xedit-hook-bridge/dist/xEditHookBridge.dll` is tracked. `git status` clean for `tools/xedit-hook-bridge/`. Installer deploys the DLL to `<MO2>/tools/xEdit/` (or wherever `daemon-adapter.ts` expects).

---

## Phase P8 — End-to-end acceptance + version sync + release dry-run

Goal: prove the reshape works on all three harnesses against a clean MO2.

- [ ] P8.1 Run `scripts/bump-version.sh 0.1.0-rc.1` and confirm all manifests sync.
- [ ] P8.2 **Acceptance run — OpenCode**: start `opencode` from `D:\awesome-bgs-mod-master\.artifacts\mo2`. In a clean session, ask "tell me about your superpowers". Bootstrap skill should load. Then ask the agent to invoke `xedit-conflict-audit` on a known fixture (LOAD001 case). Verify the audit succeeds, audit log written to `.opencode/artifacts/xedit-mcp/audit/<date>.jsonl`.
- [ ] P8.3 **Acceptance run — Claude Code**: install the plugin via local marketplace. Same session test. Verify `.mcp.json` resolution worked.
- [ ] P8.4 **Acceptance run — Codex**: install the plugin via Codex CLI. Same session test. Verify `.mcp.json` resolution worked OR fall back to relative paths and document.
- [ ] P8.5 **First-run bootstrap acceptance**: from a fresh OpenCode profile without MO2 detected, invoke `setting-up-bgs-modding-environment` skill. Verify:
  - MO2 absence is detected and surfaced.
  - User-handled install path produces a guide.
  - Agent-handled install path (with user consent) runs the installer.
  - "No MO2 needed" path exits cleanly.
- [ ] P8.6 Preserve acceptance evidence under `.opencode/artifacts/reshape/acceptance/` (gitignored; for our records).
- [ ] P8.7 Tag `v0.1.0-rc.1` on the feature branch.
- [ ] P8.8 Final commit: `chore(reshape): v0.1.0-rc.1 acceptance evidence + release notes (P8)`.

**P8 acceptance:** all three harnesses pass the smoke test against the dev MO2 sandbox. Bootstrap skill loads on session start. First-run skill correctly handles MO2 detection + install paths.

---

## Risks & open questions

| Risk | Mitigation |
|---|---|
| Codex `${CLAUDE_PLUGIN_ROOT}` substitution not supported | P4.5 smoke-test; fall back to relative `./tools/xedit-mcp/dist/index.js`. Document. |
| OpenCode plugin-return `mcp:` field undocumented but observed | Use the `config:` hook merge as primary (documented surface); add `mcp:` return as belt-and-suspenders. |
| `BB-84C/TES5Edit` release zip layout may not match expected paths | P6.2 — inspect actual release artifact in dev sandbox; adjust extraction path. |
| Pre-built `dist/` in git inflates repo diff | Accept; matches `oh-my-opencode-slim` pattern; `prepare` script handles direct checkout. |
| Phase-0 stub skills moved to `docs/internal/future-skills/` may rot | Acceptable; they're design notes, not promises. Future plans rebuild them as real skills. |
| `agents/repo-bootstrap` deletion loses dev context | Content absorbed into `docs/internal/repo-bootstrap.md` (P3.11) before delete. |
| Templates deletion loses dev-log scaffolds | Acceptable per user decision; future skills (`writing-modpack-devlog`, `writing-modpack-changelog`) will create files at runtime. Flag as v0.2 follow-up. |
| `.opencode/plugins/` gitignore exception may break unrelated `.opencode/` files | Test with `git check-ignore -v` on each new tracked file. |

---

## Out of scope (explicit non-goals)

- Cursor and Gemini harness support — deferred to v0.2.
- Publishing to npm registry — install is git-package only (matches `obra/superpowers` v0.1 approach).
- Additional MCPs (`nexus-metadata`, `loot-metadata`, `translation-memory`) — specs preserved under `docs/internal/mcp-specs/`; implementation deferred.
- Public marketplace publication — only the in-repo `marketplace.json` is created.
- Refactoring `tools/xedit-mcp/` internals — kept as-is; only path scrubbing in P5.

---

## Implementer guidance

- Use `superpowers:executing-plans` (sequential) or `superpowers:subagent-driven-development` (parallel where independent).
- Phases P1, P2, P3 are largely independent and can be parallelized via `@fixer` subagents per phase IF orchestrator splits cleanly.
- Phase P4 depends on P1+P2 done.
- Phase P5 depends on P3 (some files move).
- Phase P6 depends on P5 (path-clean scripts).
- Phase P7 depends on P6.
- Phase P8 sequential, last.
- Commit at the end of each phase; do not bundle phases.
- After each phase: update this plan with `- [x]` checkmarks and a short note inline.
