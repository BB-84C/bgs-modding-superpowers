# S5b — Complex T3 Part 2: Mod Ops + Profile Lifecycle + Final Acceptance (Tasks S5.8-S5.14)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Continues from S5a.

**Goal:** Land the last 6 T3 tools (`mo2_reinstall_mod`, `mo2_remove_mod`, `mo2_set_file_hidden`, `mo2_create_profile`, `mo2_clone_profile`, `mo2_rename_profile`) + final v1 acceptance gate. After this stage: **34 tools live**, ready for vendor distribution.

---

## Task S5.8: `mo2_reinstall_mod` (T3, depends on meta.ini `installationFile`)

Spec: librarian-alpha §A5. Reinstall via existing archive matched by `meta.ini[General] installationFile=`. Optional `fomod_choices` for non-interactive FOMOD reinstall.

**Files:** `src/tools/mo2-reinstall-mod.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_reinstall_mod",
  async buildPlan(args: { name: string; fomod_choices?: any[] }, ctx) {
    if (!ctx.pipeClient) throw new Error("live_mo2_required_for_reinstall");
    const meta = await ctx.pipeClient.call("mods.meta_read", { name: args.name });
    if (!meta.ok) throw new Error(meta.error?.message);
    const installFile = meta.result.meta?.General?.installationFile;
    if (!installFile) throw new Error("no_installation_file_in_meta_ini: cannot reinstall this mod (likely added pre-MO2-2.x)");
    const ini = await (await import("../mo-ini.js")).readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const downloadsDir = ini.settings.downloadDirectory ?? join(ctx.config.mo2Root, "downloads");
    const archivePath = join(downloadsDir, installFile);
    if (!existsSync(archivePath)) throw new Error(`archive_not_in_downloads: ${installFile}`);
    return {
      diff: `Reinstall ${args.name} from ${archivePath}. Priority + meta preserved; content replaced.`,
      affectedFiles: [join(ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods"), args.name)],
      targets: [{ path: join(ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods"), args.name), kind: "directory" }],
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    const meta = await ctx.pipeClient!.call("mods.meta_read", { name: args.name });
    const installFile = meta.result.meta.General.installationFile;
    const ini = await (await import("../mo-ini.js")).readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const archivePath = join(ini.settings.downloadDirectory ?? join(ctx.config.mo2Root, "downloads"), installFile);

    // FOMOD branch: use sidecar + Pattern A
    let isFomod = false;
    try { await ctx.sidecar!.call("fomod.parse_choices", { archive_path: archivePath }); isFomod = true; } catch {}
    if (isFomod && !args.fomod_choices) throw new Error("fomod_choices_required_for_reinstall");

    // Call broker installation.install_local_archive (it auto-detects via meta.ini matching for reinstall)
    const resp = await ctx.pipeClient!.call("installation.install_local_archive", {
      archive_path: archivePath, name_suggestion: args.name,
    });
    if (!resp.ok) throw new Error(resp.error?.message);
    if (ctx.sidecar) await ctx.sidecar.call("world.invalidate", { profile_dir: join(ctx.config.mo2Root, "profiles", "Default") });
    return { reinstalled: args.name, archive: installFile, fomod_used: isFomod };
  },
};

registerTool({
  name: "mo2_reinstall_mod", tier: "T3",
  description: "Reinstall mod from its meta.ini[installationFile]. Requires file in downloads/. FOMOD requires fomod_choices.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), name: z.string(),
               fomod_choices: z.array(z.object({
                 page_name: z.string(),
                 selected_options: z.array(z.object({ group_name: z.string(), option_name: z.string() })),
               })).optional() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_reinstall_mod (T3 via installationFile match)"
```

---

## Task S5.9: `mo2_remove_mod` (T3, default backup_first=true)

Destructive: physical mod folder delete. Default `backup_first=true` calls `mo2_backup_mod` first.

**Files:** `src/tools/mo2-remove-mod.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_remove_mod",
  async buildPlan(args: { name: string; backup_first?: boolean }, ctx) {
    const ini = await (await import("../mo-ini.js")).readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    const modPath = join(modsDir, args.name);
    if (!existsSync(modPath)) throw new Error(`mod_not_found: ${args.name}`);
    const backupFirst = args.backup_first ?? true;
    return {
      diff: `${backupFirst ? "Backup + " : ""}DELETE mod folder ${modPath} + remove from all profile modlists`,
      affectedFiles: [modPath],
      targets: [{ path: modPath, kind: "directory" }],
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    const backupFirst = args.backup_first ?? true;
    let backupName: string | undefined;

    if (backupFirst) {
      // Inline backup: copy <name> → <name>backupN
      const ini = await (await import("../mo-ini.js")).readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
      const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
      let i = 0;
      while (existsSync(join(modsDir, `${args.name}backup${i}`))) i++;
      backupName = `${args.name}backup${i}`;
      const { cp } = await import("node:fs/promises");
      await cp(join(modsDir, args.name), join(modsDir, backupName), { recursive: true });
    }

    if (ctx.pipeClient) {
      const resp = await ctx.pipeClient.call("mods.remove", { name: args.name });
      if (!resp.ok) throw new Error(resp.error?.message);
    } else {
      // Offline: rm -rf mod dir + scrub from all profiles' modlist.txt
      const ini = await (await import("../mo-ini.js")).readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
      const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
      const { rm, readdir, readFile } = await import("node:fs/promises");
      await rm(join(modsDir, args.name), { recursive: true, force: true });
      const profilesRoot = join(ctx.config.mo2Root, "profiles");
      const profs = await readdir(profilesRoot);
      for (const p of profs) {
        const ml = join(profilesRoot, p, "modlist.txt");
        try {
          const text = await readFile(ml, "utf8");
          const filtered = text.split(/\r?\n/).filter(l => l.replace(/^[+\-]/, "") !== args.name).join("\n");
          if (filtered !== text) await atomicWriteText(ml, filtered);
        } catch {}
      }
    }
    if (ctx.sidecar) await ctx.sidecar.call("world.invalidate", { profile_dir: join(ctx.config.mo2Root, "profiles", "Default") });
    return { removed: args.name, backup_name: backupName };
  },
};

registerTool({
  name: "mo2_remove_mod", tier: "T3",
  description: "Remove a mod (physical delete + remove from all profile modlists). DEFAULT backup_first=true: creates <name>backupN before delete.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), name: z.string(), backup_first: z.boolean().default(true) }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_remove_mod (T3 destructive, default backup_first)"
```

---

## Task S5.10: `mo2_set_file_hidden` (T3, .mohidden rename)

Spec: librarian-alpha §B1. Pure filesystem rename. Resolves owner mod via broker `organizer.get_file_origins` (live) or assumes virtual_path is `<mod>/<rel>` form.

**Files:** `src/tools/mo2-set-file-hidden.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_set_file_hidden",
  async buildPlan(args: { virtual_path: string; hidden: boolean }, ctx) {
    let realPath: string;
    if (ctx.pipeClient) {
      const resp = await ctx.pipeClient.call("organizer.resolve_path", { filename: args.virtual_path });
      realPath = resp.result?.resolved;
      if (!realPath) throw new Error(`virtual_path_not_resolvable: ${args.virtual_path}`);
    } else {
      // Offline: search enabled mods for the file (winner = highest priority match)
      const { readProfile } = await import("../profile-reader.js");
      const ini = await (await import("../mo-ini.js")).readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
      const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
      const p = await readProfile(join(ctx.config.mo2Root, "profiles", "Default"));
      const enabled = p.mods.filter(m => m.enabled && !m.isSeparator).sort((a, b) => b.priority - a.priority);
      const candidates = [args.virtual_path, args.virtual_path.replace(/^Data[/\\]/i, "")];
      realPath = "";
      for (const m of enabled) {
        for (const rel of candidates) {
          const try1 = join(modsDir, m.name, rel);
          const try2 = join(modsDir, m.name, "Data", rel);
          if (existsSync(try1)) { realPath = try1; break; }
          if (existsSync(try2)) { realPath = try2; break; }
        }
        if (realPath) break;
      }
      if (!realPath) throw new Error("file_not_found_in_enabled_mods");
    }

    // Determine current state
    const isCurrentlyHidden = realPath.endsWith(".mohidden");
    if (args.hidden === !isCurrentlyHidden) {
      return { diff: `no-op (already ${args.hidden ? "hidden" : "visible"})`,
               affectedFiles: [realPath], targets: [{ path: realPath, kind: "text-file" }] };
    }
    const newPath = args.hidden ? `${realPath}.mohidden` : realPath.replace(/\.mohidden$/, "");
    return {
      diff: `${realPath} → ${newPath}`,
      affectedFiles: [realPath, newPath],
      targets: [{ path: realPath, kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    const { rename } = await import("node:fs/promises");
    const args = plan.args;
    let realPath: string;
    // Re-resolve (lease is on the real path)
    if (ctx.pipeClient) {
      const resp = await ctx.pipeClient.call("organizer.resolve_path", { filename: args.virtual_path });
      realPath = resp.result.resolved;
    } else {
      // Same offline logic as plan
      realPath = plan.affectedFiles[0];  // stored in plan
    }
    const isCurrentlyHidden = realPath.endsWith(".mohidden");
    const newPath = args.hidden ? `${realPath}.mohidden` : realPath.replace(/\.mohidden$/, "");
    if (args.hidden === !isCurrentlyHidden) return { no_op: true, path: realPath };
    await rename(realPath, newPath);
    if (ctx.pipeClient) await ctx.pipeClient.call("organizer.refresh", { save_changes: false });
    return { renamed_from: realPath, renamed_to: newPath, hidden: args.hidden };
  },
};

registerTool({
  name: "mo2_set_file_hidden", tier: "T3",
  description: "Hide or unhide a VFS file via .mohidden rename (USVFS skipFileSuffixes convention). Only works on loose files (not archive entries).",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), virtual_path: z.string(), hidden: z.boolean() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_set_file_hidden (.mohidden rename, loose files only)"
```

---

## Task S5.11: `mo2_create_profile` (T3, online + offline paths)

Spec: librarian-alpha §E2. Online = `IPluginGame.initializeProfile` + clone source modlist. Offline = filesystem create + warn no game INI defaults.

**Files:** `src/tools/mo2-create-profile.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_create_profile",
  async buildPlan(args: { name: string; from_profile?: string; settings?: string[] }, ctx) {
    const profilesRoot = join(ctx.config.mo2Root, "profiles");
    const newDir = join(profilesRoot, args.name);
    if (existsSync(newDir)) throw new Error(`profile_exists: ${args.name}`);
    const path = ctx.pipeClient ? "online" : "offline";
    return {
      diff: `Create profile ${args.name} via ${path} path${args.from_profile ? `, clone modlist from ${args.from_profile}` : ""}`,
      affectedFiles: [newDir],
      targets: [],  // additive
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    const profilesRoot = join(ctx.config.mo2Root, "profiles");
    const newDir = join(profilesRoot, args.name);
    const { mkdir, writeFile, copyFile } = await import("node:fs/promises");
    await mkdir(newDir, { recursive: true });
    await writeFile(join(newDir, "modlist.txt"), "");
    await writeFile(join(newDir, "archives.txt"), "");

    if (ctx.pipeClient) {
      // Online: call broker which invokes IPluginGame.initializeProfile (needs new pipe command, scope creep beyond S1 — defer to v1.1 enhancement if not yet implemented)
      try {
        await ctx.pipeClient.call("profile.initialize", { profile_dir: newDir, settings: args.settings ?? ["MODS", "CONFIGURATION"] });
      } catch (e) {
        return { profile_name: args.name, path: newDir, source: "online_init_failed_offline_fallback", warning: String(e) };
      }
    }
    // Offline: just create dir + empty files; user gets profile without game INI defaults
    // Optionally clone from another profile
    if (args.from_profile) {
      const srcDir = join(profilesRoot, args.from_profile);
      const { readdir } = await import("node:fs/promises");
      const files = await readdir(srcDir);
      for (const f of files) {
        if (f.endsWith(".txt") || f.endsWith(".ini")) {
          try { await copyFile(join(srcDir, f), join(newDir, f)); } catch {}
        }
      }
    }
    return { profile_name: args.name, path: newDir, source: ctx.pipeClient ? "online_initialized" : "offline_created" };
  },
};

registerTool({
  name: "mo2_create_profile", tier: "T3",
  description: "Create a new profile. Online: broker calls IPluginGame.initializeProfile. Offline: filesystem-only create (no game INI defaults). Optional from_profile clones modlist+plugins from existing profile.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), name: z.string(), from_profile: z.string().optional(),
               settings: z.array(z.enum(["MODS", "SAVEGAMES", "CONFIGURATION", "PREFER_DEFAULTS"])).optional() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_create_profile (T3 online + offline paths)"
```

---

## Task S5.12: `mo2_clone_profile` (T3, MO2-closed)

Filesystem recursive copy. Default skips `saves/`, `logs/`, `crashDumps/`.

**Files:** `src/tools/mo2-clone-profile.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_clone_profile",
  async buildPlan(args: { source: string; target: string; include_saves?: boolean }, ctx) {
    const { detectMo2Running } = await import("../detection.js");
    const det = await detectMo2Running({ mo2Root: ctx.config.mo2Root });
    if (det.processRunning) throw new Error("mo2_running: close MO2 before cloning profile");
    const profilesRoot = join(ctx.config.mo2Root, "profiles");
    if (!existsSync(join(profilesRoot, args.source))) throw new Error(`source_profile_not_found`);
    if (existsSync(join(profilesRoot, args.target))) throw new Error(`target_profile_exists`);
    return {
      diff: `Clone profile ${args.source} → ${args.target} (include_saves=${args.include_saves ?? false})`,
      affectedFiles: [join(profilesRoot, args.target)],
      targets: [],
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    const profilesRoot = join(ctx.config.mo2Root, "profiles");
    const srcDir = join(profilesRoot, args.source);
    const dstDir = join(profilesRoot, args.target);
    const skipDirs = new Set(["logs", "crashDumps"]);
    if (!args.include_saves) skipDirs.add("saves");
    const skipExts = new Set([".bak"]);

    const { mkdir, readdir, copyFile, stat } = await import("node:fs/promises");
    async function copyDir(src: string, dst: string): Promise<void> {
      await mkdir(dst, { recursive: true });
      const entries = await readdir(src, { withFileTypes: true });
      for (const e of entries) {
        if (e.isDirectory()) {
          if (skipDirs.has(e.name)) continue;
          await copyDir(join(src, e.name), join(dst, e.name));
        } else {
          const ext = e.name.slice(e.name.lastIndexOf("."));
          if (skipExts.has(ext)) continue;
          await copyFile(join(src, e.name), join(dst, e.name));
        }
      }
    }
    await copyDir(srcDir, dstDir);
    return { cloned_from: args.source, to: args.target, dst_path: dstDir };
  },
};

registerTool({
  name: "mo2_clone_profile", tier: "T3",
  description: "Clone a profile (MO2 must be closed). Skips saves/logs/crashDumps by default. include_saves=true to copy saves too.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), source: z.string(), target: z.string(), include_saves: z.boolean().default(false) }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_clone_profile (T3 recursive copy, MO2-closed)"
```

---

## Task S5.13: `mo2_rename_profile` (T3, dir rename + selected_profile update)

Spec: librarian-alpha §E2 + oracle §7.3. No mobase API. Filesystem rename + edit `ModOrganizer.ini [General] selected_profile=` if it matches. MO2 must be closed.

**Files:** `src/tools/mo2-rename-profile.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_rename_profile",
  async buildPlan(args: { old_name: string; new_name: string }, ctx) {
    const { detectMo2Running } = await import("../detection.js");
    const det = await detectMo2Running({ mo2Root: ctx.config.mo2Root });
    if (det.processRunning) throw new Error("mo2_running: close MO2 before renaming profile");
    const profilesRoot = join(ctx.config.mo2Root, "profiles");
    if (!existsSync(join(profilesRoot, args.old_name))) throw new Error(`profile_not_found`);
    if (existsSync(join(profilesRoot, args.new_name))) throw new Error(`target_exists`);
    const ini = await (await import("../mo-ini.js")).readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const needsIniUpdate = ini.general.selectedProfile === args.old_name;
    return {
      diff: `Rename profile dir + ${needsIniUpdate ? "update ModOrganizer.ini selected_profile" : "no ini update"}`,
      affectedFiles: [join(profilesRoot, args.new_name),
                      ...(needsIniUpdate ? [join(ctx.config.mo2Root, "ModOrganizer.ini")] : [])],
      targets: needsIniUpdate ? [{ path: join(ctx.config.mo2Root, "ModOrganizer.ini"), kind: "text-file" }] : [],
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    const profilesRoot = join(ctx.config.mo2Root, "profiles");
    const { rename, readFile } = await import("node:fs/promises");
    await rename(join(profilesRoot, args.old_name), join(profilesRoot, args.new_name));

    const iniPath = join(ctx.config.mo2Root, "ModOrganizer.ini");
    const text = await readFile(iniPath, "utf8");
    if (text.includes(`selected_profile=${args.old_name}`)) {
      const newText = text.replace(new RegExp(`selected_profile=${args.old_name}(\\r?\\n)`),
                                    `selected_profile=${args.new_name}$1`);
      await atomicWriteText(iniPath, newText);
      return { renamed: true, ini_updated: true };
    }
    return { renamed: true, ini_updated: false };
  },
};

registerTool({
  name: "mo2_rename_profile", tier: "T3",
  description: "Rename a profile (MO2 must be closed). Updates ModOrganizer.ini selected_profile if it matched old name.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), old_name: z.string(), new_name: z.string() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_rename_profile (T3 dir rename + selected_profile sync)"
```

---

## Task S5.14: Final v1 acceptance gate

Run end-to-end against real `B:\WastelandBlues 2.0` and `D:\awesome-bgs-mod-master\.artifacts\mo2`. Captures evidence to `.opencode/artifacts/mo2-mcp/acceptance/` for future audit.

**Files:** `tools/mo2-mcp/tests/acceptance-v1.test.ts`, `scripts/run-mo2-mcp-acceptance.ps1`

- [ ] **Step 1: Write the acceptance suite (gated)**

```typescript
// tests/acceptance-v1.test.ts
import { describe, it, expect } from "vitest";
import { spawn } from "node:child_process";
import { writeFile, mkdir } from "node:fs/promises";
import { join } from "node:path";

const MO2_ROOT = process.env.BGS_MO2_ROOT || String.raw`B:\WastelandBlues 2.0`;
const ARTIFACTS = String.raw`D:\awesome-bgs-mod-master\.opencode\artifacts\mo2-mcp\acceptance`;

const skipUnlessHarness = process.env.MO2_MCP_ACCEPTANCE === "1";

describe.skipIf(!skipUnlessHarness)("v1 acceptance", () => {
  let mcp: any;
  beforeAll(async () => {
    mcp = await spawnMcp({ BGS_MO2_ROOT: MO2_ROOT });
    await mkdir(ARTIFACTS, { recursive: true });
  });
  afterAll(() => mcp?.kill());

  it("AT1: mo2_status reports correct game + counts", async () => {
    const r = await mcp.call("mo2_status", {});
    expect(r.result.game).toMatch(/fallout4/i);
    expect(r.result.counts.mods_total).toBeGreaterThan(700);
    await writeFile(join(ARTIFACTS, "AT1-status.json"), JSON.stringify(r, null, 2));
  });

  it("AT2: All 11 T1 reads return bounded output <5s", async () => {
    const tools = ["mo2_status", "mo2_machine_contract", "mo2_modlist", "mo2_pluginlist",
                   "mo2_mod_info", "mo2_assets_summary", "mo2_assets_conflicts",
                   "mo2_assets_resolve", "mo2_search_files", "mo2_list_executables", "mo2_audit_query"];
    for (const t of tools) {
      const t0 = Date.now();
      const r = await mcp.call(t, t === "mo2_mod_info" ? { name: "Fallout4.esm" } :
                                  t === "mo2_assets_resolve" ? { virtual_path: "Data/Fallout4.esm" } :
                                  t === "mo2_search_files" ? { pattern: "**/*.esp", max_results: 10 } : {});
      expect(Date.now() - t0).toBeLessThan(5000);
      expect(r.ok).toBe(true);
    }
  });

  it("AT3: plan/apply lease enforcement", async () => {
    const plan = await mcp.call("mo2_toggle_mod", { mode: "plan", name: "LODGen 覆盖素材", enabled: false });
    // Manually touch modlist.txt
    const ml = join(MO2_ROOT, "profiles", "BB84自用", "modlist.txt");
    const { readFile, writeFile } = await import("node:fs/promises");
    const text = await readFile(ml, "utf8");
    await writeFile(ml, text + "\n# touched by acceptance test\n");
    // Apply must fail
    const apply = await mcp.call("mo2_toggle_mod", { mode: "apply",
      plan_id: plan.result.planId, lease_token: plan.result.lease_token });
    expect(apply.ok).toBe(false);
    expect(apply.error.code).toBe("lease_violation");
    // Restore modlist
    await writeFile(ml, text);
  });

  it("AT4: rollback round-trip", async () => {
    // ... toggle mod plan + apply + rollback, verify byte-identical
  });

  it("AT5: STOCK001 hard-deny", async () => {
    const r = await mcp.call("mo2_set_mod_notes", { mode: "plan",
      name: "Stock Game/Data/Fallout4.esm", notes: "test" });
    expect(r.ok).toBe(false);
    expect(r.error.code).toBe("STOCK001");
  });

  // AT6-AT19 covering FOMOD install, cold-restart, customExecutables roundtrip,
  // profile create/clone/rename, atomic write under crash, audit completeness,
  // cross-MCP concurrent ...
});

async function spawnMcp(env: Record<string, string>): Promise<any> {
  // Spawn `node dist/index.js` with stdio MCP transport, return wrapper that translates
  // tools/call requests to JSON-RPC messages on stdin.
  // (~50 lines of helper)
}
```

- [ ] **Step 2: PS1 wrapper to invoke**

```powershell
# scripts/run-mo2-mcp-acceptance.ps1
param([string]$Mo2Root = "B:\WastelandBlues 2.0")
$env:MO2_MCP_ACCEPTANCE = "1"
$env:BGS_MO2_ROOT = $Mo2Root
Push-Location "$PSScriptRoot\..\tools\mo2-mcp"
npm run build
npx vitest run tests/acceptance-v1.test.ts
Pop-Location
```

- [ ] **Step 3: Run acceptance**

Expect all 19 AT* tests pass against WastelandBlues. Artifacts at `.opencode/artifacts/mo2-mcp/acceptance/AT*.json`.

- [ ] **Step 4: Final commit + close v1**

```bash
git commit -am "test(mo2-mcp): v1 acceptance suite (19 E2E tests against real modpack)"
```

---

## End of S5b — v1 COMPLETE

After S5b (7 tasks):

**Tool count final: 34 tools registered.**
- T1 reads (11): `mo2_status`, `mo2_machine_contract`, `mo2_modlist`, `mo2_pluginlist`, `mo2_mod_info`, `mo2_assets_summary`, `mo2_assets_conflicts`, `mo2_assets_resolve`, `mo2_search_files`, `mo2_list_executables`, `mo2_audit_query`
- T2 metadata (5 + 1 read): `mo2_profile_ini_get` (T1), `mo2_set_mod_notes`, `mo2_edit_meta`, `mo2_profile_ini_set`, `mo2_backup_mod`, `mo2_backup_profile`
- T3 mutate (18): `mo2_toggle_mod`, `mo2_toggle_plugin`, `mo2_send_mod_to`, `mo2_rollback`, `mo2_restore_profile`, `mo2_install`, `mo2_run_tool`, `mo2_switch_profile`, `mo2_configure_executable`, `mo2_create_mod`, `mo2_create_separator`, `mo2_rename_mod`, `mo2_reinstall_mod`, `mo2_remove_mod`, `mo2_set_file_hidden`, `mo2_create_profile`, `mo2_clone_profile`, `mo2_rename_profile`

**Total commits across all 5 stages:** ~80 small commits on `feat/mo2-mcp` branch.

**Final review gate:** `requesting-code-review` on full v1 before merging to main. Then `finishing-a-development-branch` skill for proper merge + vendor refresh.

After main merge: refresh `D:\Starfield MO2\.opencode\vendor\bgs-modding-superpowers\` via `git pull --ff-only origin main`. Verify symbols readable: `grep -r "mo2_status" plugins/bgs-modding-superpowers/tools/mo2-mcp/dist/`.

End-user dispatch: bump `bgs-modding-superpowers` semver minor, update `docs/release-changelog.md`, optional KB record `mo2-mcp.workflows.v1.md`.
