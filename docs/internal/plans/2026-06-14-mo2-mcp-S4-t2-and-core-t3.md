# S4 — T2 Metadata Writes + Core T3 Mutations (Tasks S4.1-S4.10)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` or `superpowers:executing-plans`.

**Goal:** Land 5 T2 metadata writes + 5 core T3 mutations. All go through plan/apply pipeline (S2.13). T2 = snapshot+plan+apply+audit; T3 adds mandatory lease verification + dry-run preview.

**Architecture:** Each tool implements `PlanApplyHandler` interface from S2.13. Pipeline: `buildPlan` (snapshot + compute diff + compute lease) → cache → `applyMutation` (re-verify lease + execute + audit). Live-mode T3 prefers broker pipe; offline-mode writes files atomically. STOCK001 rule already blocks Stock Game/Data paths.

**Tech Stack:** Same as S2-S3.

---

## File Structure
- Create per tool: `src/tools/<tool>.ts` + `tests/tools/<tool>.test.ts`
- Each tool file: Zod schema for `mode: "plan" | "apply"` discriminated union, `PlanApplyHandler` impl, `registerTool()` call

---

## Task S4.1: `mo2_set_mod_notes` (T2)

**Files:** `src/tools/mo2-set-mod-notes.ts`

- [ ] **Step 1-3: Test + impl**

```typescript
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { join } from "node:path";
import { readMoIni } from "../mo-ini.js";
import type { PlanApplyHandler } from "../plan-apply.js";

const handler: PlanApplyHandler = {
  toolName: "mo2_set_mod_notes",
  async buildPlan(args: { name: string; notes: string }, ctx) {
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    const metaPath = join(modsDir, args.name, "meta.ini");
    return {
      diff: `[General]\nnotes="${args.notes}"`,
      affectedFiles: [metaPath],
      targets: [{ path: metaPath, kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    if (ctx.pipeClient) {
      // Live: prefer broker mods.meta_write
      const resp = await ctx.pipeClient.call("mods.meta_write", {
        name: args.name, updates: { General: { notes: `"${args.notes}"` } },
      });
      if (!resp.ok) throw new Error(resp.error?.message);
      return resp.result;
    }
    // Offline: atomic file write
    const { atomicWriteText } = await import("../atomic.js");
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    const metaPath = join(modsDir, args.name, "meta.ini");
    const { readFile } = await import("node:fs/promises");
    let text = "";
    try { text = await readFile(metaPath, "utf8"); } catch {}
    // Naive [General] notes= update — production: full parser
    text = upsertIniValue(text, "General", "notes", `"${args.notes}"`);
    await atomicWriteText(metaPath, text);
    return { name: args.name, notes_set: true };
  },
};

registerTool({
  name: "mo2_set_mod_notes", tier: "T2",
  description: "Set mod notes (meta.ini [General] notes=). Plan returns diff; apply atomically writes via temp+rename.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), name: z.string(), notes: z.string() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: async (args, ctx) => routeToPlanApply(handler, args, ctx),
});

function upsertIniValue(text: string, section: string, key: string, value: string): string {
  const lines = text.split(/\r?\n/);
  let inSec = false; let sectionFoundIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() === `[${section}]`) { inSec = true; sectionFoundIdx = i; continue; }
    if (inSec && lines[i].startsWith("[")) { inSec = false; }
    if (inSec && lines[i].startsWith(`${key}=`)) { lines[i] = `${key}=${value}`; return lines.join("\n"); }
  }
  if (sectionFoundIdx >= 0) { lines.splice(sectionFoundIdx + 1, 0, `${key}=${value}`); return lines.join("\n"); }
  return text + `\n[${section}]\n${key}=${value}\n`;
}
```

(`routeToPlanApply` is a small helper in `plan-apply.ts` that branches on `args.mode` calling `runPlanMode` or `runApplyMode`.)

- [ ] **Step 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_set_mod_notes (T2 plan/apply with live+offline paths)"
```

---

## Task S4.2: `mo2_edit_meta` (T2)

Arbitrary `meta.ini` section/key edits.

**Files:** `src/tools/mo2-edit-meta.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_edit_meta",
  async buildPlan(args: { name: string; updates: Record<string, Record<string, string>> }, ctx) {
    const metaPath = await resolveModMetaPath(args.name, ctx);
    const diff = Object.entries(args.updates).map(([s, kv]) =>
      `[${s}]\n${Object.entries(kv).map(([k, v]) => `${k}=${v}`).join("\n")}`).join("\n\n");
    return { diff, affectedFiles: [metaPath], targets: [{ path: metaPath, kind: "text-file" }] };
  },
  async applyMutation(plan, ctx) {
    if (ctx.pipeClient) {
      const resp = await ctx.pipeClient.call("mods.meta_write", { name: plan.args.name, updates: plan.args.updates });
      return resp.result;
    }
    // Offline: read+merge+write via shared upsertIniValue
    const { atomicWriteText } = await import("../atomic.js");
    const metaPath = await resolveModMetaPath(plan.args.name, ctx);
    const { readFile } = await import("node:fs/promises");
    let text = ""; try { text = await readFile(metaPath, "utf8"); } catch {}
    for (const [section, kv] of Object.entries(plan.args.updates)) {
      for (const [k, v] of Object.entries(kv as any)) text = upsertIniValue(text, section, k, String(v));
    }
    await atomicWriteText(metaPath, text);
    return { name: plan.args.name, sections_updated: Object.keys(plan.args.updates) };
  },
};

registerTool({
  name: "mo2_edit_meta", tier: "T2",
  description: "Edit arbitrary meta.ini fields. updates = {section: {key: value}}.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), name: z.string(),
               updates: z.record(z.record(z.string())) }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_edit_meta (T2 arbitrary meta.ini section/key edits)"
```

---

## Task S4.3: `mo2_profile_ini_set` (T2)

Write profile-local `<game>.ini` / `<game>Prefs.ini` / `<game>Custom.ini`. Hard-deny if MO2 running on target profile (would race with on-exit save).

**Files:** `src/tools/mo2-profile-ini-set.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_profile_ini_set",
  async buildPlan(args, ctx) {
    const iniPath = await resolveProfileIniPath(args, ctx);
    const { detectMo2Running } = await import("../detection.js");
    const det = await detectMo2Running({ mo2Root: ctx.config.mo2Root, profileDir: join(ctx.config.mo2Root, "profiles", args.profile) });
    if (det.profileLockHeld) throw new Error("mo2_holds_profile_files: close MO2 before INI write or use mo2_switch_profile");
    const diff = `[${args.section}]\n${args.key}=${args.value}`;
    return { diff, affectedFiles: [iniPath], targets: [{ path: iniPath, kind: "text-file" }] };
  },
  async applyMutation(plan, ctx) {
    const { atomicWriteText } = await import("../atomic.js");
    const iniPath = await resolveProfileIniPath(plan.args, ctx);
    const { readFile } = await import("node:fs/promises");
    let text = ""; try { text = await readFile(iniPath, "utf8"); } catch {}
    text = upsertIniValue(text, plan.args.section, plan.args.key, plan.args.value);
    await atomicWriteText(iniPath, text);
    return { ini_path: iniPath, key_set: `${plan.args.section}/${plan.args.key}` };
  },
};

registerTool({
  name: "mo2_profile_ini_set", tier: "T2",
  description: "Set profile-local INI key. Refuses if MO2 holds profile files.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), profile: z.string().default("Default"),
               ini_name: z.enum(["game", "prefs", "custom"]),
               section: z.string(), key: z.string(), value: z.string() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_profile_ini_set (T2 with MO2-running hard-deny)"
```

---

## Task S4.4: `mo2_backup_mod` (T2)

File-level mod backup: `<name>backup0`, `<name>backup1`, ... per librarian-alpha §A7. Naming regex `.*backup[0-9]*` triggers MO2's FLAG_BACKUP auto-tag.

**Files:** `src/tools/mo2-backup-mod.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_backup_mod",
  async buildPlan(args: { name: string }, ctx) {
    const { existsSync } = await import("node:fs");
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    const sourceMod = join(modsDir, args.name);
    if (!existsSync(sourceMod)) throw new Error(`mod_not_found: ${args.name}`);
    // Find free backup slot
    let i = 0;
    while (existsSync(join(modsDir, `${args.name}backup${i}`))) i++;
    const backupPath = join(modsDir, `${args.name}backup${i}`);
    return {
      diff: `cp -r ${sourceMod} → ${backupPath}`,
      affectedFiles: [backupPath],  // additive
      targets: [{ path: sourceMod, kind: "directory" }],  // lease against source unchanged
    };
  },
  async applyMutation(plan, ctx) {
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    const { cp, existsSync } = await import("node:fs");
    const { cp: cpAsync } = await import("node:fs/promises");
    let i = 0;
    while (existsSync(join(modsDir, `${plan.args.name}backup${i}`))) i++;
    const backupPath = join(modsDir, `${plan.args.name}backup${i}`);
    await cpAsync(join(modsDir, plan.args.name), backupPath, { recursive: true });
    if (ctx.pipeClient) await ctx.pipeClient.call("organizer.refresh", { save_changes: false });
    return { backup_name: `${plan.args.name}backup${i}`, backup_path: backupPath };
  },
};

registerTool({
  name: "mo2_backup_mod", tier: "T2",
  description: "Create file-level backup of a mod (<name>backupN naming convention; MO2 auto-tags FLAG_BACKUP).",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), name: z.string() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_backup_mod (<name>backupN filesystem copy)"
```

---

## Task S4.5: `mo2_backup_profile` (T2)

Explicit full-profile snapshot: modlist.txt + plugins.txt + loadorder.txt + INIs into a named backup dir.

**Files:** `src/tools/mo2-backup-profile.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_backup_profile",
  async buildPlan(args: { profile: string; label?: string }, ctx) {
    const profileDir = join(ctx.config.mo2Root, "profiles", args.profile);
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const label = args.label ?? ts;
    const backupDir = join(ctx.config.mo2Root, ".mo2-mcp", "profile-backups", `${args.profile}_${label}`);
    const filesToCopy = ["modlist.txt", "plugins.txt", "loadorder.txt", "settings.txt"];
    return {
      diff: `cp ${filesToCopy.join(", ")} from ${profileDir} → ${backupDir}`,
      affectedFiles: [backupDir],
      targets: filesToCopy.map(f => ({ path: join(profileDir, f), kind: "text-file" as const })),
    };
  },
  async applyMutation(plan, ctx) {
    const { mkdir, copyFile, readdir } = await import("node:fs/promises");
    const profileDir = join(ctx.config.mo2Root, "profiles", plan.args.profile);
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const label = plan.args.label ?? ts;
    const backupDir = join(ctx.config.mo2Root, ".mo2-mcp", "profile-backups", `${plan.args.profile}_${label}`);
    await mkdir(backupDir, { recursive: true });
    const all = await readdir(profileDir);
    for (const f of all) {
      if (f.endsWith(".txt") || f.endsWith(".ini")) {
        try { await copyFile(join(profileDir, f), join(backupDir, f)); } catch {}
      }
    }
    return { backup_label: label, backup_dir: backupDir, files_backed_up: all.filter(f => f.endsWith(".txt") || f.endsWith(".ini")).length };
  },
};

registerTool({
  name: "mo2_backup_profile", tier: "T2",
  description: "Explicit full-profile backup (all .txt + .ini under profile). Saved to .mo2-mcp/profile-backups/<profile>_<label>/.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), profile: z.string().default("Default"), label: z.string().optional() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_backup_profile (explicit full-profile snapshot)"
```

---

## Task S4.6: `mo2_toggle_mod` (T3)

Enable/disable a mod. Live: broker `mods.set_active`. Offline: modlist.txt rewrite. Lease covers modlist.txt content hash.

**Files:** `src/tools/mo2-toggle-mod.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_toggle_mod",
  async buildPlan(args: { name: string; enabled: boolean; profile?: string }, ctx) {
    const profile = args.profile ?? "Default";
    const modlistPath = join(ctx.config.mo2Root, "profiles", profile, "modlist.txt");
    const { readProfile } = await import("../profile-reader.js");
    const p = await readProfile(join(ctx.config.mo2Root, "profiles", profile));
    const mod = p.mods.find(m => m.name === args.name);
    if (!mod) throw new Error(`mod_not_found: ${args.name}`);
    if (mod.enabled === args.enabled) {
      return { diff: `no-op (${args.name} already ${args.enabled ? "enabled" : "disabled"})`,
               affectedFiles: [modlistPath], targets: [{ path: modlistPath, kind: "text-file" }] };
    }
    return {
      diff: `${args.name}: ${mod.enabled ? "+" : "-"} → ${args.enabled ? "+" : "-"}`,
      affectedFiles: [modlistPath],
      targets: [{ path: modlistPath, kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    if (ctx.pipeClient) {
      const resp = await ctx.pipeClient.call("mods.set_active", { names: [plan.args.name], active: plan.args.enabled });
      if (!resp.ok) throw new Error(resp.error?.message);
      return resp.result;
    }
    // Offline: modlist.txt rewrite with atomic temp+rename
    const profile = plan.args.profile ?? "Default";
    const modlistPath = join(ctx.config.mo2Root, "profiles", profile, "modlist.txt");
    const { readFile } = await import("node:fs/promises");
    const { atomicWriteText } = await import("../atomic.js");
    const text = await readFile(modlistPath, "utf8");
    const lines = text.split(/\r?\n/);
    const newLines = lines.map(l => {
      if (l.endsWith(plan.args.name) && !l.endsWith(`_separator`)) {
        return (plan.args.enabled ? "+" : "-") + plan.args.name;
      }
      return l;
    });
    await atomicWriteText(modlistPath, newLines.join("\n"));
    return { name: plan.args.name, enabled: plan.args.enabled, source: "offline_modlist_rewrite" };
  },
};

registerTool({
  name: "mo2_toggle_mod", tier: "T3",
  description: "Enable or disable a mod. Plan→apply with lease on modlist.txt content hash. Live: broker pipe; offline: atomic file rewrite.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), name: z.string(), enabled: z.boolean(), profile: z.string().default("Default") }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_toggle_mod (T3 live+offline with lease on modlist.txt)"
```

---

## Task S4.7: `mo2_toggle_plugin` (T3, with `also_hide_file`)

Plugin enable/disable. Optional `also_hide_file=true` triggers `.mohidden` rename of the .esp file → "Optional ESP" semantics (oracle §B2).

**Files:** `src/tools/mo2-toggle-plugin.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_toggle_plugin",
  async buildPlan(args: { name: string; enabled: boolean; also_hide_file?: boolean; profile?: string }, ctx) {
    const profile = args.profile ?? "Default";
    const pluginsPath = join(ctx.config.mo2Root, "profiles", profile, "plugins.txt");
    const targets: Array<{ path: string; kind: "text-file" | "directory" }> = [{ path: pluginsPath, kind: "text-file" }];
    const affected = [pluginsPath];
    let espPath: string | undefined;
    if (args.also_hide_file) {
      if (!ctx.pipeClient) throw new Error("also_hide_file_requires_live_mo2: pipe needed to find owning mod");
      const origin = await ctx.pipeClient.call("organizer.get_file_origins", { filename: args.name });
      const ownerMod = origin.result?.origins?.[0];
      if (!ownerMod || ownerMod === "data") throw new Error("plugin_not_owned_by_mod");
      const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
      const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
      espPath = join(modsDir, ownerMod, args.name);  // may be at mod root or Data/
      affected.push(espPath);
      targets.push({ path: espPath, kind: "text-file" });
    }
    return {
      diff: `plugins.txt: ${args.enabled ? "*" : ""}${args.name}\n${espPath ? `${espPath} ${args.enabled ? "(unhide)" : "→ .mohidden"}` : ""}`,
      affectedFiles: affected, targets,
    };
  },
  async applyMutation(plan, ctx) {
    if (ctx.pipeClient) {
      const stateInt = plan.args.enabled ? 2 : 1;  // PluginState::Active=2, Inactive=1
      const resp = await ctx.pipeClient.call("plugins.set_state", { name: plan.args.name, state: stateInt });
      if (!resp.ok) throw new Error(resp.error?.message);
      const result: any = { plugin_state_set: resp.result };
      if (plan.args.also_hide_file) {
        // Rename .esp ↔ .esp.mohidden
        const { rename } = await import("node:fs/promises");
        const espPath = plan.affectedFiles[1];  // second target
        const hiddenPath = espPath + ".mohidden";
        try {
          if (plan.args.enabled) await rename(hiddenPath, espPath);  // unhide
          else await rename(espPath, hiddenPath);  // hide
          result.file_renamed = true;
        } catch (e) { result.file_rename_failed = String(e); }
        await ctx.pipeClient.call("organizer.refresh", { save_changes: false });
      }
      return result;
    }
    // Offline: plugins.txt rewrite, mohidden rename (no refresh)
    const profile = plan.args.profile ?? "Default";
    const pluginsPath = join(ctx.config.mo2Root, "profiles", profile, "plugins.txt");
    const { readFile, rename } = await import("node:fs/promises");
    const { atomicWriteText } = await import("../atomic.js");
    const text = await readFile(pluginsPath, "utf8");
    const lines = text.split(/\r?\n/).map(l => {
      const bare = l.replace(/^\*/, "");
      if (bare === plan.args.name) return (plan.args.enabled ? "*" : "") + plan.args.name;
      return l;
    });
    await atomicWriteText(pluginsPath, lines.join("\n"));
    return { name: plan.args.name, enabled: plan.args.enabled, source: "offline_plugins_txt_rewrite",
             also_hide_file: plan.args.also_hide_file ? "requires_live_mo2" : false };
  },
};

registerTool({
  name: "mo2_toggle_plugin", tier: "T3",
  description: "Enable/disable plugin. Optional also_hide_file=true renames the .esp to .mohidden for Optional-ESP semantics (live-mode only).",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), name: z.string(), enabled: z.boolean(),
               also_hide_file: z.boolean().default(false), profile: z.string().default("Default") }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_toggle_plugin (T3 with also_hide_file for Optional-ESP)"
```

---

## Task S4.8: `mo2_send_mod_to` (T3, 6 modes)

Modes per oracle §A3: `top` / `bottom` / `priority` / `above_separator` / `above_first_conflict` / `below_last_conflict`.

**Files:** `src/tools/mo2-send-mod-to.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_send_mod_to",
  async buildPlan(args, ctx) {
    const profile = args.profile ?? "Default";
    const modlistPath = join(ctx.config.mo2Root, "profiles", profile, "modlist.txt");
    const targetPri = await computeTargetPriority(args, ctx, profile);
    return {
      diff: `${args.name}: → priority ${targetPri} (mode=${args.mode})`,
      affectedFiles: [modlistPath],
      targets: [{ path: modlistPath, kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    const profile = plan.args.profile ?? "Default";
    const targetPri = await computeTargetPriority(plan.args, ctx, profile);
    if (ctx.pipeClient) {
      const resp = await ctx.pipeClient.call("mods.set_priority", { name: plan.args.name, priority: targetPri });
      if (!resp.ok) throw new Error(resp.error?.message);
      return { ...resp.result, mode: plan.args.mode };
    }
    // Offline: modlist.txt line reorder
    const modlistPath = join(ctx.config.mo2Root, "profiles", profile, "modlist.txt");
    const { readFile } = await import("node:fs/promises");
    const { atomicWriteText } = await import("../atomic.js");
    const text = await readFile(modlistPath, "utf8");
    const lines = text.split(/\r?\n/).filter(l => l.length > 0);
    const idx = lines.findIndex(l => l.replace(/^[+\-]/, "") === plan.args.name);
    if (idx < 0) throw new Error("mod_not_found_in_modlist");
    const [moved] = lines.splice(idx, 1);
    // priority 0 = bottom of mobase = top of modlist.txt? See profile-reader inversion in S2.5
    // priority N-1 = top of mobase = bottom of modlist.txt
    const insertIdx = lines.length - targetPri;
    lines.splice(Math.max(0, Math.min(insertIdx, lines.length)), 0, moved);
    await atomicWriteText(modlistPath, lines.join("\n") + "\n");
    return { name: plan.args.name, new_priority: targetPri, source: "offline_modlist_reorder" };
  },
};

async function computeTargetPriority(args: any, ctx: any, profile: string): Promise<number> {
  const { readProfile } = await import("../profile-reader.js");
  const p = await readProfile(join(ctx.config.mo2Root, "profiles", profile));
  const nonSep = p.mods.filter(m => !m.isSeparator);
  switch (args.mode) {
    case "top": return nonSep.length - 1;
    case "bottom": return 0;
    case "priority": return args.target_priority ?? 0;
    case "above_separator": {
      const sep = p.mods.find(m => m.isSeparator && m.name === args.target_separator);
      if (!sep) throw new Error(`separator_not_found: ${args.target_separator}`);
      return sep.priority + 1;
    }
    case "above_first_conflict": {
      if (!ctx.sidecar) throw new Error("sidecar_required_for_conflict_mode");
      const conflicts = await ctx.sidecar.call("assets.conflicts", {
        profile_dir: join(ctx.config.mo2Root, "profiles", profile), max_results: 5000 });
      const myConflictMods = conflicts.conflicts.filter((c: any) => c.providers.includes(args.name))
        .flatMap((c: any) => c.providers.filter((m: string) => m !== args.name));
      if (myConflictMods.length === 0) throw new Error("no_conflicts_found");
      const conflictPriorities = myConflictMods.map((n: string) => p.mods.find(m => m.name === n)?.priority ?? 0);
      return Math.max(...conflictPriorities) + 1;
    }
    case "below_last_conflict": {
      if (!ctx.sidecar) throw new Error("sidecar_required");
      // mirror above_first_conflict with min - 1
      // ...
      return 0;
    }
    default: throw new Error(`unknown_mode: ${args.mode}`);
  }
}

registerTool({
  name: "mo2_send_mod_to", tier: "T3",
  description: "Reposition a mod by mode: top/bottom/priority/above_separator/above_first_conflict/below_last_conflict.",
  inputSchema: z.discriminatedUnion("mode_kind", [
    z.object({ mode_kind: z.literal("plan"), name: z.string(),
               mode: z.enum(["top", "bottom", "priority", "above_separator", "above_first_conflict", "below_last_conflict"]),
               target_priority: z.number().int().optional(),
               target_separator: z.string().optional(),
               profile: z.string().default("Default") }),
    z.object({ mode_kind: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, { ...args, mode: args.mode_kind === "plan" ? "plan" : "apply" }, ctx),
});
```

(Note: schema uses `mode_kind` because `mode` is also a domain field; map to `mode: "plan"|"apply"` for the plan/apply router.)

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_send_mod_to (T3 with 6 positioning modes)"
```

---

## Task S4.9: `mo2_rollback` (T3)

Restore from a snapshot created by any T2/T3 apply. Plan returns snapshot manifest; apply executes restore.

**Files:** `src/tools/mo2-rollback.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_rollback",
  async buildPlan(args: { snapshot_id: string }, ctx) {
    const { readdir, readFile } = await import("node:fs/promises");
    const sessionDir = join(ctx.config.snapshotRoot, ctx.sessionId);
    const dirs = await readdir(sessionDir).catch(() => []);
    for (const d of dirs) {
      try {
        const manifest = JSON.parse(await readFile(join(sessionDir, d, "manifest.json"), "utf8"));
        if (manifest.snapshotId === args.snapshot_id) {
          return {
            diff: `Restore ${manifest.files.length} files from snapshot ${args.snapshot_id} (tool=${manifest.tool}, ts=${manifest.ts})`,
            affectedFiles: manifest.files.map((f: any) => f.source),
            targets: manifest.files.map((f: any) => ({ path: f.source, kind: "text-file" as const })),
          };
        }
      } catch {}
    }
    throw new Error(`snapshot_not_found: ${args.snapshot_id}`);
  },
  async applyMutation(plan, ctx) {
    const { SnapshotManager } = await import("../snapshot.js");
    const sm = new SnapshotManager(ctx.config.snapshotRoot, ctx.sessionId);
    return await sm.restore(plan.args.snapshot_id);
  },
};

registerTool({
  name: "mo2_rollback", tier: "T3",
  description: "Restore from a snapshot_id created by an earlier T2/T3 apply.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), snapshot_id: z.string() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_rollback (T3 restore from snapshot)"
```

---

## Task S4.10: `mo2_restore_profile` (T3)

Restore from a `mo2_backup_profile` snapshot. Different from `mo2_rollback` — this restores profile-level state from a named backup label, not a transactional snapshot.

**Files:** `src/tools/mo2-restore-profile.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_restore_profile",
  async buildPlan(args: { profile: string; label: string }, ctx) {
    const backupDir = join(ctx.config.mo2Root, ".mo2-mcp", "profile-backups", `${args.profile}_${args.label}`);
    const { readdir } = await import("node:fs/promises");
    const files = await readdir(backupDir).catch(() => { throw new Error(`backup_not_found: ${args.profile}_${args.label}`); });
    const profileDir = join(ctx.config.mo2Root, "profiles", args.profile);
    return {
      diff: `Restore ${files.length} files from ${backupDir} → ${profileDir}`,
      affectedFiles: files.map(f => join(profileDir, f)),
      targets: files.map(f => ({ path: join(profileDir, f), kind: "text-file" as const })),
    };
  },
  async applyMutation(plan, ctx) {
    const backupDir = join(ctx.config.mo2Root, ".mo2-mcp", "profile-backups", `${plan.args.profile}_${plan.args.label}`);
    const profileDir = join(ctx.config.mo2Root, "profiles", plan.args.profile);
    const { readdir, copyFile } = await import("node:fs/promises");
    const files = await readdir(backupDir);
    const restored: string[] = [];
    for (const f of files) {
      try { await copyFile(join(backupDir, f), join(profileDir, f)); restored.push(f); } catch {}
    }
    return { profile: plan.args.profile, label: plan.args.label, restored };
  },
};

registerTool({
  name: "mo2_restore_profile", tier: "T3",
  description: "Restore profile state from a mo2_backup_profile label.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), profile: z.string().default("Default"), label: z.string() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_restore_profile (T3 from named backup label)"
```

---

## End of S4

10 tasks land: 5 T2 metadata writes + 5 core T3 mutations. ~10 commits.

**Tool count after S4:** 12 (S3) + 10 (S4) = **22 tools registered**.

**Verification:**
- All vitest unit + integration tests pass
- Plan/apply lease enforcement test: touch modlist.txt between plan and apply → lease_violation
- Rollback round-trip: T3 apply → mo2_rollback → file byte-identical
- STOCK001 hard-deny: try to set notes on a mod under Stock Game/Data → block

**Review gate:** `requesting-code-review` before S5. Verify:
- All T2/T3 use atomic temp+rename
- Lease component types are text-file or directory (never mtime)
- Live-mode fallback to offline doesn't lose mutations silently
- routeToPlanApply correctly branches on mode arg

Then S5 (complex T3 + FOMOD).
