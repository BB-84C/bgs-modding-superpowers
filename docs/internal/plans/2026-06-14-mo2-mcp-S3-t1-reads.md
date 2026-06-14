# S3 — T1 Read Tools (Tasks S3.1-S3.12)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` or `superpowers:executing-plans`.

**Goal:** Register 12 T1 (read-only, always-allowed) tools in the MCP tool registry. All tools audit but no plan/apply, no snapshot, no lease.

**Architecture:** T1 tools use `ToolContext` (config + pipeClient? + sidecar?) and return JSON results. Profile/plugin reads use the TS native reader (`profile-reader.ts` from S2.5) — no subprocess overhead. Asset tools delegate to the Python sidecar (`assets.summary`/`assets.conflicts`/`assets.resolve_file`). Bounded output everywhere (charrdge pattern: `max_*` args + `truncated` flag).

**Tech Stack:** Same as S2 — TypeScript, Zod schemas, vitest.

---

## File Structure
- Create per tool: `src/tools/<tool_name>.ts`
- Tests per tool: `tests/tools/<tool_name>.test.ts`
- Modify: `src/index.ts` — import all tool registrations
- Reuse: `src/profile-reader.ts`, `src/mo-ini.ts`, `src/pipe-client.ts`, `src/sidecar-client.ts`, `src/audit.ts`

Each tool file is self-contained: Zod input schema + handler + side-effect call to `registerTool()`.

---

## Task S3.1: `mo2_status`

Reports: instance path, game, profile, online/offline (3-tier detection results), counts, permission ceiling.

**Files:** `src/tools/mo2-status.ts`, `tests/tools/mo2-status.test.ts`

- [ ] **Step 1-3: Test + impl**

```typescript
// src/tools/mo2-status.ts
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { detectMo2Running } from "../detection.js";
import { readProfile } from "../profile-reader.js";
import { readMoIni } from "../mo-ini.js";
import { join } from "node:path";

const inputSchema = z.object({});

registerTool({
  name: "mo2_status", tier: "T1",
  description: "Report MO2 instance state: paths, game, active profile, MO2-running detection (3-tier ladder), mod/plugin counts, MCP permission ceiling.",
  inputSchema,
  handler: async (_args, ctx) => {
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const profileDir = join(ctx.config.mo2Root, "profiles", ctx.config.allowedProfiles[0]);
    const detection = await detectMo2Running({ mo2Root: ctx.config.mo2Root, profileDir });
    const profile = await readProfile(profileDir).catch(() => null);
    return {
      ok: true,
      result: {
        mo2_root: ctx.config.mo2Root,
        game: ini.general.game,
        game_name: ini.general.gameName,
        game_path: ini.general.gamePath,
        profile: profile?.name,
        permission_ceiling: ctx.config.permissionCeiling,
        detection: {
          process_running: detection.processRunning,
          shared_memory_present: detection.sharedMemoryPresent,
          profile_lock_held: detection.profileLockHeld,
          mo2_pid: detection.pid,
          online: detection.online,
        },
        counts: profile ? {
          mods_total: profile.mods.length,
          mods_enabled: profile.mods.filter(m => m.enabled).length,
          plugins_total: profile.plugins.length,
          plugins_enabled: profile.plugins.filter(p => p.enabled).length,
        } : null,
        broker_connected: !!ctx.pipeClient,
        sidecar_ready: !!ctx.sidecar,
      },
      error: null,
    };
  },
});
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): mo2_status (3-tier detection + counts + ceiling)"
```

---

## Task S3.2: `mo2_machine_contract`

Charrdge pattern (oracle Unique catches): return paths only, agent does its own follow-up reads. Saves token budget.

**Files:** `src/tools/mo2-machine-contract.ts`

- [ ] **Steps 1-3:**

```typescript
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { readMoIni } from "../mo-ini.js";
import { join } from "node:path";
import { existsSync } from "node:fs";

registerTool({
  name: "mo2_machine_contract", tier: "T1",
  description: "Paths-only snapshot (charrdge pattern): returns absolute paths the agent can read natively without further MCP calls. Cheap; agent uses its Read tool on returned paths.",
  inputSchema: z.object({ only_enabled: z.boolean().default(false) }).strict(),
  handler: async (args, ctx) => {
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const profileDir = join(ctx.config.mo2Root, "profiles", ctx.config.allowedProfiles[0]);
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    const { readdir } = await import("node:fs/promises");
    const allMods = await readdir(modsDir, { withFileTypes: true }).catch(() => []);
    return {
      ok: true,
      result: {
        profile_list_paths: {
          modlist_txt: join(profileDir, "modlist.txt"),
          plugins_txt: join(profileDir, "plugins.txt"),
          loadorder_txt: join(profileDir, "loadorder.txt"),
          profile_dir: profileDir,
        },
        profile_inis: {
          game_ini: existsSync(join(profileDir, `${ini.general.game}.ini`)) ? join(profileDir, `${ini.general.game}.ini`) : null,
          gameprefs_ini: existsSync(join(profileDir, `${ini.general.game}Prefs.ini`)) ? join(profileDir, `${ini.general.game}Prefs.ini`) : null,
        },
        mod_organizer_ini: join(ctx.config.mo2Root, "ModOrganizer.ini"),
        archive_search_roots: allMods.filter(d => d.isDirectory()).map(d => ({
          mod_name: d.name,
          mod_root_abs: join(modsDir, d.name),
          effective_data_root_abs: existsSync(join(modsDir, d.name, "Data")) ? join(modsDir, d.name, "Data") : join(modsDir, d.name),
          is_data_subdir_layout: existsSync(join(modsDir, d.name, "Data")),
        })),
      },
      error: null,
    };
  },
});
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): mo2_machine_contract (paths-only snapshot, charrdge pattern)"
```

---

## Task S3.3: `mo2_modlist`

Native TS read of modlist.txt. Optional pipe enrichment for display_name (live only).

**Files:** `src/tools/mo2-modlist.ts`

- [ ] **Steps 1-3:**

```typescript
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { readProfile } from "../profile-reader.js";
import { join } from "node:path";

registerTool({
  name: "mo2_modlist", tier: "T1",
  description: "Read modlist.txt. Returns mods with name, priority, enabled, is_separator. Native TS read; if MO2 is live and enrich=true, adds display_name via mobase.",
  inputSchema: z.object({
    profile: z.string().default("Default"),
    enrich: z.boolean().default(false),
  }).strict(),
  handler: async (args, ctx) => {
    const profileDir = join(ctx.config.mo2Root, "profiles", args.profile);
    const profile = await readProfile(profileDir);
    let mods: any[] = profile.mods;
    if (args.enrich && ctx.pipeClient) {
      const resp = await ctx.pipeClient.call("mods.list", {}).catch(() => null);
      if (resp?.ok && resp.result?.mods) {
        const enrichMap = new Map<string, any>(resp.result.mods.map((m: any) => [m.name, m]));
        mods = mods.map(m => ({ ...m, live_priority: enrichMap.get(m.name)?.priority ?? null }));
      }
    }
    return { ok: true, result: { profile: args.profile, mods }, error: null };
  },
});
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): mo2_modlist (TS native read + optional pipe enrich)"
```

---

## Task S3.4: `mo2_pluginlist`

**Files:** `src/tools/mo2-pluginlist.ts`

- [ ] **Steps 1-3:**

```typescript
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { readProfile } from "../profile-reader.js";
import { join } from "node:path";

registerTool({
  name: "mo2_pluginlist", tier: "T1",
  description: "Read plugins.txt. Returns plugins with name + enabled (* prefix = enabled per MO2/FO4 convention). Optional pipe enrich adds masters/load_order/origin/flags.",
  inputSchema: z.object({ profile: z.string().default("Default"), enrich: z.boolean().default(false) }).strict(),
  handler: async (args, ctx) => {
    const profileDir = join(ctx.config.mo2Root, "profiles", args.profile);
    const profile = await readProfile(profileDir);
    let plugins: any[] = profile.plugins;
    if (args.enrich && ctx.pipeClient) {
      const resp = await ctx.pipeClient.call("plugins.list", {}).catch(() => null);
      if (resp?.ok && resp.result?.plugins) {
        const map = new Map<string, any>(resp.result.plugins.map((p: any) => [p.name, p]));
        plugins = plugins.map(p => ({ ...p, ...map.get(p.name) }));
      }
    }
    return { ok: true, result: { profile: args.profile, plugins }, error: null };
  },
});
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): mo2_pluginlist (TS native + optional pipe enrich)"
```

---

## Task S3.5: `mo2_mod_info`

Single mod detail: meta.ini fields, file count, archive count.

**Files:** `src/tools/mo2-mod-info.ts`

- [ ] **Steps 1-3:**

```typescript
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { readMoIni } from "../mo-ini.js";
import { join } from "node:path";

registerTool({
  name: "mo2_mod_info", tier: "T1",
  description: "Single mod detail: meta.ini fields, file count, archive count, absolute path.",
  inputSchema: z.object({ name: z.string() }).strict(),
  handler: async (args, ctx) => {
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    const modPath = join(modsDir, args.name);
    const { stat, readFile, readdir } = await import("node:fs/promises");
    try { await stat(modPath); }
    catch { return { ok: false, error: { code: "mod_not_found", message: args.name } }; }

    let meta: Record<string, any> = {};
    try {
      const metaText = await readFile(join(modPath, "meta.ini"), "utf8");
      // Reuse mo-ini parser shape; meta.ini is similar key=value
      const sectionMatch = metaText.matchAll(/^\[(.+)\]\s*\n([^[]*)/gm);
      for (const m of sectionMatch) {
        const section: Record<string, string> = {};
        m[2].split(/\r?\n/).forEach(line => {
          const eq = line.indexOf("=");
          if (eq > 0) section[line.slice(0, eq).trim()] = line.slice(eq + 1);
        });
        meta[m[1]] = section;
      }
    } catch { /* no meta.ini */ }

    let fileCount = 0; let archiveCount = 0;
    async function walk(d: string): Promise<void> {
      const entries = await readdir(d, { withFileTypes: true });
      for (const e of entries) {
        const full = join(d, e.name);
        if (e.isDirectory()) await walk(full);
        else {
          fileCount++;
          if (/\.(ba2|bsa)$/i.test(e.name)) archiveCount++;
        }
      }
    }
    await walk(modPath);

    return { ok: true, result: {
      name: args.name, absolute_path: modPath, meta, file_count: fileCount, archive_count: archiveCount
    }, error: null };
  },
});
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): mo2_mod_info (meta.ini parse + file/archive counts)"
```

---

## Task S3.6: `mo2_assets_summary`

Delegate to Python sidecar `assets.summary`.

**Files:** `src/tools/mo2-assets-summary.ts`

- [ ] **Steps 1-3:**

```typescript
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { join } from "node:path";

registerTool({
  name: "mo2_assets_summary", tier: "T1",
  description: "Summary counts via Python sidecar (mo2_assets_engine).",
  inputSchema: z.object({ profile: z.string().default("Default") }).strict(),
  handler: async (args, ctx) => {
    if (!ctx.sidecar) return { ok: false, error: { code: "sidecar_not_ready", message: "Python sidecar not available" } };
    const profileDir = join(ctx.config.mo2Root, "profiles", args.profile);
    const result = await ctx.sidecar.call("assets.summary", { profile_dir: profileDir });
    return { ok: true, result, error: null };
  },
});
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): mo2_assets_summary via sidecar"
```

---

## Task S3.7: `mo2_assets_conflicts`

Bounded output: `max_results` (default 10000) + `truncated` flag.

**Files:** `src/tools/mo2-assets-conflicts.ts`

- [ ] **Steps 1-3:**

```typescript
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { join } from "node:path";

registerTool({
  name: "mo2_assets_conflicts", tier: "T1",
  description: "List file conflicts via sidecar. Bounded output (max_results, default 10000). Returns truncated flag.",
  inputSchema: z.object({
    profile: z.string().default("Default"),
    max_results: z.number().int().min(1).max(50000).default(10000),
    path_prefix: z.string().optional(),
  }).strict(),
  handler: async (args, ctx) => {
    if (!ctx.sidecar) return { ok: false, error: { code: "sidecar_not_ready" } };
    const profileDir = join(ctx.config.mo2Root, "profiles", args.profile);
    const result = await ctx.sidecar.call("assets.conflicts", {
      profile_dir: profileDir, max_results: args.max_results, path_prefix: args.path_prefix,
    });
    return { ok: true, result, error: null };
  },
});
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): mo2_assets_conflicts with bounded output"
```

---

## Task S3.8: `mo2_assets_resolve`

Resolve a single virtual path to winning mod.

**Files:** `src/tools/mo2-assets-resolve.ts`

- [ ] **Steps 1-3:**

```typescript
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { join } from "node:path";

registerTool({
  name: "mo2_assets_resolve", tier: "T1",
  description: "Resolve a virtual path (e.g., 'Data/textures/foo.dds') to winner mod + provider chain via sidecar.",
  inputSchema: z.object({
    profile: z.string().default("Default"),
    virtual_path: z.string(),
  }).strict(),
  handler: async (args, ctx) => {
    if (!ctx.sidecar) return { ok: false, error: { code: "sidecar_not_ready" } };
    const profileDir = join(ctx.config.mo2Root, "profiles", args.profile);
    const result = await ctx.sidecar.call("assets.resolve_file", {
      profile_dir: profileDir, virtual_path: args.virtual_path,
    });
    return { ok: true, result, error: null };
  },
});
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): mo2_assets_resolve (single virtual path winner)"
```

---

## Task S3.9: `mo2_search_files`

Glob/regex across enabled mod trees. Bounded.

**Files:** `src/tools/mo2-search-files.ts`

- [ ] **Steps 1-3:**

```typescript
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { readProfile } from "../profile-reader.js";
import { readMoIni } from "../mo-ini.js";
import { join } from "node:path";

registerTool({
  name: "mo2_search_files", tier: "T1",
  description: "Glob/regex file search across enabled mod trees. Bounded by max_results (default 1000). Returns paths + truncated flag.",
  inputSchema: z.object({
    profile: z.string().default("Default"),
    pattern: z.string(),  // glob like "**/*.esp" or regex with regex: prefix
    max_results: z.number().int().min(1).max(10000).default(1000),
  }).strict(),
  handler: async (args, ctx) => {
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    const profile = await readProfile(join(ctx.config.mo2Root, "profiles", args.profile));
    const enabled = profile.mods.filter(m => m.enabled && !m.isSeparator);

    const isRegex = args.pattern.startsWith("regex:");
    const matcher = isRegex ? new RegExp(args.pattern.slice(6)) : null;
    const { readdir } = await import("node:fs/promises");
    const results: string[] = [];
    let truncated = false;

    outer: for (const mod of enabled) {
      const root = join(modsDir, mod.name);
      const walk = async (d: string): Promise<void> => {
        if (results.length >= args.max_results) { truncated = true; return; }
        const entries = await readdir(d, { withFileTypes: true }).catch(() => []);
        for (const e of entries) {
          if (results.length >= args.max_results) { truncated = true; return; }
          const full = join(d, e.name);
          if (e.isDirectory()) await walk(full);
          else {
            const rel = full.slice(root.length + 1).replace(/\\/g, "/");
            const matches = isRegex ? matcher!.test(rel) : globMatch(args.pattern, rel);
            if (matches) results.push(`${mod.name}/${rel}`);
          }
        }
      };
      await walk(root);
      if (truncated) break outer;
    }
    return { ok: true, result: { results, truncated, count: results.length }, error: null };
  },
});

function globMatch(pattern: string, path: string): boolean {
  const re = new RegExp("^" + pattern
    .replace(/\./g, "\\.").replace(/\*\*/g, "{{DSTAR}}").replace(/\*/g, "[^/]*")
    .replace(/\{\{DSTAR\}\}/g, ".*").replace(/\?/g, "[^/]") + "$", "i");
  return re.test(path);
}
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): mo2_search_files (glob/regex across enabled mods, bounded)"
```

---

## Task S3.10: `mo2_list_executables`

Use `mo-ini.ts` parser already wired in S2.

**Files:** `src/tools/mo2-list-executables.ts`

- [ ] **Steps 1-3:**

```typescript
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { readMoIni } from "../mo-ini.js";
import { join } from "node:path";

registerTool({
  name: "mo2_list_executables", tier: "T1",
  description: "List configured customExecutables from ModOrganizer.ini (title, binary, arguments, workingDirectory, etc.).",
  inputSchema: z.object({}).strict(),
  handler: async (_args, ctx) => {
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    return { ok: true, result: { executables: ini.customExecutables, count: ini.customExecutables.length }, error: null };
  },
});
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): mo2_list_executables"
```

---

## Task S3.11: `mo2_audit_query`

Query MCP's own audit log. Filter by date / tool / decision / plan_id.

**Files:** `src/tools/mo2-audit-query.ts`

- [ ] **Steps 1-3:**

```typescript
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

registerTool({
  name: "mo2_audit_query", tier: "T1",
  description: "Query MCP audit log. Filters: date range, tool name, decision, plan_id. Returns matching records.",
  inputSchema: z.object({
    date_from: z.string().optional(),  // YYYY-MM-DD
    date_to: z.string().optional(),
    tool: z.string().optional(),
    decision: z.enum(["ok", "refused", "plan_generated", "applied", "lease_violation", "rolled_back"]).optional(),
    plan_id: z.string().optional(),
    max_results: z.number().int().min(1).max(5000).default(500),
  }).strict(),
  handler: async (args, ctx) => {
    const files = await readdir(ctx.config.auditRoot).catch(() => []);
    const matched: any[] = [];
    let truncated = false;
    for (const f of files) {
      if (!f.endsWith(".jsonl")) continue;
      const dateMatch = f.match(/(\d{4}-\d{2}-\d{2})\.jsonl$/);
      if (!dateMatch) continue;
      if (args.date_from && dateMatch[1] < args.date_from) continue;
      if (args.date_to && dateMatch[1] > args.date_to) continue;
      const text = await readFile(join(ctx.config.auditRoot, f), "utf8");
      for (const line of text.split("\n")) {
        if (!line.trim()) continue;
        try {
          const rec = JSON.parse(line);
          if (args.tool && rec.tool !== args.tool) continue;
          if (args.decision && rec.decision !== args.decision) continue;
          if (args.plan_id && rec.planId !== args.plan_id) continue;
          matched.push(rec);
          if (matched.length >= args.max_results) { truncated = true; break; }
        } catch { /* skip */ }
      }
      if (truncated) break;
    }
    return { ok: true, result: { records: matched, count: matched.length, truncated }, error: null };
  },
});
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): mo2_audit_query (filter+bounded)"
```

---

## Task S3.12: `mo2_profile_ini_get`

Read profile-local `<game>.ini` / `<game>Prefs.ini` / `<game>Custom.ini`. Key/section query.

**Files:** `src/tools/mo2-profile-ini-get.ts`

- [ ] **Steps 1-3:**

```typescript
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { readMoIni } from "../mo-ini.js";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

registerTool({
  name: "mo2_profile_ini_get", tier: "T1",
  description: "Read profile-local game INI. Returns sections or a specific section/key value. Falls back to %DOCUMENTS%/<Game>/ if local INIs not enabled.",
  inputSchema: z.object({
    profile: z.string().default("Default"),
    ini_name: z.enum(["game", "prefs", "custom"]),  // <game>.ini / <game>Prefs.ini / <game>Custom.ini
    section: z.string().optional(),
    key: z.string().optional(),
  }).strict(),
  handler: async (args, ctx) => {
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const game = ini.general.game;
    if (!game) return { ok: false, error: { code: "no_game_set", message: "ModOrganizer.ini [General] game= missing" } };

    const fileMap = { game: `${game}.ini`, prefs: `${game}Prefs.ini`, custom: `${game}Custom.ini` };
    const fileName = fileMap[args.ini_name];
    const localPath = join(ctx.config.mo2Root, "profiles", args.profile, fileName);
    let text: string;
    let source: string;
    try { text = await readFile(localPath, "utf8"); source = "profile_local"; }
    catch {
      // Fallback: %DOCUMENTS%\<Game>\<file>
      const docs = process.env.USERPROFILE ? join(process.env.USERPROFILE, "Documents", "My Games", game) : null;
      if (!docs) return { ok: false, error: { code: "ini_not_found", message: fileName } };
      try { text = await readFile(join(docs, fileName), "utf8"); source = "documents"; }
      catch { return { ok: false, error: { code: "ini_not_found", message: fileName } }; }
    }

    // Parse with mo-ini-style flat parser
    const sections: Record<string, Record<string, string>> = {};
    let cur = "";
    for (const line of text.split(/\r?\n/)) {
      const m = line.match(/^\[(.+)\]$/);
      if (m) { cur = m[1]; sections[cur] = sections[cur] ?? {}; continue; }
      const eq = line.indexOf("=");
      if (cur && eq > 0) sections[cur][line.slice(0, eq).trim()] = line.slice(eq + 1);
    }

    if (args.section && args.key) {
      return { ok: true, result: { source, ini_name: args.ini_name, value: sections[args.section]?.[args.key] }, error: null };
    }
    if (args.section) {
      return { ok: true, result: { source, ini_name: args.ini_name, section: sections[args.section] ?? {} }, error: null };
    }
    return { ok: true, result: { source, ini_name: args.ini_name, sections }, error: null };
  },
});
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): mo2_profile_ini_get (profile-local + documents fallback)"
```

---

## End of S3

After S3 (12 tasks):

**Tools registered:** 11 T1 read tools + `mo2_profile_ini_get` (T1 but paired with `mo2_profile_ini_set` in S4 as T2 write).

**Verification:**
- All vitest unit tests pass
- Smoke `tools/list` returns 12 tools
- Each tool returns valid JSON with bounded output where applicable
- Audit records every call

**Review gate:** Run `requesting-code-review` skill. Specifically:
- Bounded output is honored everywhere (max_results, truncated)
- Sidecar-not-ready returns clean error, doesn't crash
- Pipe-not-connected gracefully degrades (enrich=true silently drops enrichment)
- Polarity correct: modlist `+` = enabled, `-` = disabled; plugins `*` = enabled

Then start S4 (T2 metadata writes + core T3 mutations).

---

## End-of-S3 acceptance gate (run before S4)

Against real `B:\WastelandBlues 2.0` (FO4, 803 mods, 421k files):

| Tool | Method | Pass |
|---|---|---|
| `mo2_status` | call | reports correct game, profile, counts, detection result |
| `mo2_machine_contract` | call | returns 803 mod entries with absolute paths |
| `mo2_modlist` | call (enrich=false) | <2s, returns 803 entries, polarity correct |
| `mo2_pluginlist` | call | returns plugins from plugins.txt with `*` polarity correct |
| `mo2_mod_info` | name="LODGen 覆盖素材" | meta.ini parsed, file_count + archive_count > 0 |
| `mo2_assets_summary` | call | sidecar responds, counts match `mo2-assets summary` CLI |
| `mo2_assets_conflicts` | max_results=100 | returns 100 conflicts + truncated=true |
| `mo2_assets_resolve` | virtual_path="Data/textures/foo.dds" | resolves to winner mod |
| `mo2_search_files` | pattern="**/*.esp", max_results=50 | returns ≤50 esp paths |
| `mo2_list_executables` | call | returns ≥1 executable (xEdit registered) |
| `mo2_audit_query` | tool="mo2_status" | returns audit records from this session |
| `mo2_profile_ini_get` | ini_name="prefs", section="Display" | returns Display section keys |

All pass → merge `feat/mo2-mcp` partial to main, refresh vendor clone, start S4.
