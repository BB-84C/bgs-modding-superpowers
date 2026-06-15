# S5a — Complex T3 Part 1: Install + Run + Switch + Configure + Create + Rename (Tasks S5.1-S5.7)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` or `superpowers:executing-plans`.

**Goal:** Land 7 complex T3 tools: `mo2_install` (FOMOD Pattern A orchestration), `mo2_run_tool`, `mo2_switch_profile` (cold-restart), `mo2_configure_executable`, `mo2_create_mod`, `mo2_create_separator`, `mo2_rename_mod` (cross-profile sync).

**Architecture:** Same plan/apply pattern + heavy orchestration. `mo2_install` is the most complex (sidecar FOMOD parse → staging → broker createMod → file move → meta.ini write → refresh). `mo2_switch_profile` choreographs `system.shutdown` → MO2 dead detection → relaunch → ready detection → sidecar `world.invalidate`.

---

## Task S5.1: `mo2_install` (T3, FOMOD Pattern A complete)

Reference: oracle traps §4.1-§4.5. Three install paths: simple archive (no FOMOD info.xml), FOMOD interactive (refused — requires live wizard), FOMOD non-interactive (Pattern A with `fomod_choices` arg).

**Files:** `src/tools/mo2-install.ts`

- [ ] **Step 1: Failing test (simple archive path)**

```typescript
import { describe, it, expect } from "vitest";
import { spawn } from "node:child_process";

describe("mo2_install simple archive", () => {
  it("plan returns staged file count + conflict report", async () => {
    // ... setup fixture archive without FOMOD info.xml ...
    const result = await callTool("mo2_install", { mode: "plan", archive_path: "/tmp/test.7z", mod_name: "TestMod" });
    expect(result.ok).toBe(true);
    expect(result.result.staged_files).toBeGreaterThan(0);
    expect(result.result.has_fomod).toBe(false);
  });

  it("FOMOD archive with no choices arg returns fomod_choices_required", async () => {
    const result = await callTool("mo2_install", { mode: "plan", archive_path: "/tmp/fomod.7z", mod_name: "FomodMod" });
    expect(result.ok).toBe(false);
    expect(result.error.code).toBe("fomod_choices_required");
    expect(result.error.fomod_tree).toBeDefined();
  });
});
```

- [ ] **Step 2: Run fail**

- [ ] **Step 3: Implement (orchestration)**

```typescript
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import { existsSync } from "node:fs";
import type { PlanApplyHandler } from "../plan-apply.js";
import { atomicWriteText } from "../atomic.js";

const handler: PlanApplyHandler = {
  toolName: "mo2_install",
  async buildPlan(args, ctx) {
    if (!ctx.sidecar) throw new Error("sidecar_required_for_install");
    const installId = randomUUID();
    const stagingDir = join(ctx.config.mo2Root, ".mo2-mcp", "staging", installId);

    // 1. Detect FOMOD via sidecar
    let fomodTree: any = null;
    let resolvedFiles: any[] = [];
    let isFomod = false;
    try {
      fomodTree = await ctx.sidecar.call("fomod.parse_choices", { archive_path: args.archive_path });
      isFomod = true;
    } catch (e: any) {
      if (!String(e.message).includes("not_a_fomod") && !String(e.message).includes("info.xml")) throw e;
    }
    if (isFomod && !args.fomod_choices) {
      throw new Error(`fomod_choices_required:${JSON.stringify(fomodTree)}`);
    }
    if (isFomod) {
      const resolved = await ctx.sidecar.call("fomod.resolve_files", {
        archive_path: args.archive_path, choices: args.fomod_choices,
      });
      resolvedFiles = resolved.files;
    } else {
      // Simple archive: extract everything (via sidecar or 7z) into staging
      // For brevity, assume sidecar exposes archive.extract_all
      const extracted = await ctx.sidecar.call("archive.extract_all", { archive_path: args.archive_path, dest: stagingDir });
      resolvedFiles = extracted.files;
    }

    // 2. Compute conflict report against current profile
    const profileDir = join(ctx.config.mo2Root, "profiles", args.profile ?? "Default");
    const conflictReport = await ctx.sidecar.call("install.conflict_preview", {
      profile_dir: profileDir, staged_files: resolvedFiles, target_priority: args.target_priority ?? "bottom",
    });

    // 3. Compute target mods/ destination
    const modsDir = (await import("../mo-ini.js")).readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini")).then(i => i.settings.modDirectory ?? join(ctx.config.mo2Root, "mods"));
    const destPath = join(await modsDir, args.mod_name);
    if (existsSync(destPath)) throw new Error(`mod_name_exists: ${args.mod_name}`);

    return {
      diff: `Install ${args.mod_name} (${resolvedFiles.length} files). FOMOD=${isFomod}. Conflicts: ${conflictReport.summary}`,
      affectedFiles: [destPath, join(profileDir, "modlist.txt")],
      targets: [{ path: profileDir + "/modlist.txt", kind: "text-file" }],  // lease against modlist
    };
  },

  async applyMutation(plan, ctx) {
    const args = plan.args;
    const installId = plan.snapshotId ?? randomUUID();  // reuse if planted in plan
    const stagingDir = join(ctx.config.mo2Root, ".mo2-mcp", "staging", installId);

    // 1. Stage files (sidecar re-extracts to stagingDir using fomod_choices if applicable)
    if (args.fomod_choices) {
      await ctx.sidecar!.call("install.stage_fomod", {
        archive_path: args.archive_path, choices: args.fomod_choices, staging_dir: stagingDir,
      });
    } else {
      await ctx.sidecar!.call("archive.extract_all", { archive_path: args.archive_path, dest: stagingDir });
    }

    // 2. Create empty mod via broker (live) or filesystem (offline)
    const profile = args.profile ?? "Default";
    const ini = await (await import("../mo-ini.js")).readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    const destPath = join(modsDir, args.mod_name);

    if (ctx.pipeClient) {
      const created = await ctx.pipeClient.call("installation.create_mod_from_directory", { name: args.mod_name });
      if (!created.ok) throw new Error(created.error?.message);
    } else {
      const { mkdir } = await import("node:fs/promises");
      await mkdir(destPath, { recursive: true });
    }

    // 3. Atomic move staged content to destination (oracle §4.4)
    const { rename, cp } = await import("node:fs/promises");
    try {
      await rename(stagingDir, destPath);  // same-volume fast path
    } catch (e: any) {
      if (e.code === "EXDEV") { await cp(stagingDir, destPath, { recursive: true }); /* cleanup staging */ }
      else throw e;
    }

    // 4. Write meta.ini (oracle §4.3 fields)
    const meta = [
      "[General]",
      `gameName=${ini.general.game ?? ""}`,
      `modid=${args.nexus_mod_id ?? 0}`,
      `version=${args.version ?? ""}`,
      `installationFile=${args.archive_path.split(/[/\\]/).pop() ?? ""}`,
      `nexusFileStatus=1`,
      `repository=Nexus`,
      `category="${args.category ?? 0}"`,
      `notes=""`,
      `validated=true`,
    ].join("\n");
    await atomicWriteText(join(destPath, "meta.ini"), meta);

    // 5. Register in modlist.txt at target priority
    const modlistPath = join(ctx.config.mo2Root, "profiles", profile, "modlist.txt");
    const { readFile } = await import("node:fs/promises");
    const text = await readFile(modlistPath, "utf8");
    const newLine = `+${args.mod_name}\n`;
    const updated = args.target_priority === "top" ? newLine + text : text + newLine;
    await atomicWriteText(modlistPath, updated);

    // 6. Live refresh + sidecar invalidate
    if (ctx.pipeClient) await ctx.pipeClient.call("organizer.refresh", { save_changes: true });
    if (ctx.sidecar) await ctx.sidecar.call("world.invalidate", { profile_dir: join(ctx.config.mo2Root, "profiles", profile) });

    return { mod_name: args.mod_name, dest_path: destPath, fomod_used: !!args.fomod_choices };
  },
};

registerTool({
  name: "mo2_install", tier: "T3",
  description: "Install a mod from local archive (.zip/.7z/.rar). Supports FOMOD non-interactive via fomod_choices arg. Pattern A: sidecar parse → staging → createMod → move → meta.ini → register.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), archive_path: z.string(), mod_name: z.string(),
               profile: z.string().default("Default"),
               target_priority: z.union([z.literal("top"), z.literal("bottom"), z.number().int()]).default("bottom"),
               fomod_choices: z.array(z.object({
                 page_name: z.string(),
                 selected_options: z.array(z.object({ group_name: z.string(), option_name: z.string() })),
               })).optional(),
               nexus_mod_id: z.number().optional(), version: z.string().optional(), category: z.string().optional() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Step 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_install with full FOMOD Pattern A orchestration"
```

---

## Task S5.2: `mo2_run_tool` (T3, live-only via pipe)

Spec: librarian-alpha §C2. CLI `ModOrganizer.exe -p exe <title>` for offline; `IOrganizer.startApplication` for live.

**Files:** `src/tools/mo2-run-tool.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_run_tool",
  async buildPlan(args: { title: string; wait?: boolean }, ctx) {
    const ini = await (await import("../mo-ini.js")).readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const exe = ini.customExecutables.find(e => e.title === args.title);
    if (!exe) throw new Error(`executable_not_found: ${args.title} (configured: ${ini.customExecutables.map(e => e.title).join(", ")})`);
    return {
      diff: `Run ${exe.binary} ${exe.arguments ?? ""} via MO2 VFS (wait=${args.wait ?? false})`,
      affectedFiles: [],  // running a tool doesn't directly mutate profile state
      targets: [],
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    if (ctx.pipeClient) {
      const resp = await ctx.pipeClient.call("organizer.start_application", {
        executable: args.title, args: [], cwd: "", profile: "", forcedCustomOverwrite: "", ignoreCustomOverwrite: false,
      });
      if (!resp.ok) throw new Error(resp.error?.message);
      if (args.wait) {
        const wait = await ctx.pipeClient.call("organizer.wait_for_application", { handle: resp.result.handle, refresh: true });
        return { handle: resp.result.handle, exit_code: wait.result?.exit_code, success: wait.result?.success };
      }
      return { handle: resp.result.handle, waiting: false };
    }
    // Offline: spawn ModOrganizer.exe directly
    const { spawn } = await import("node:child_process");
    const child = spawn(join(ctx.config.mo2Root, "ModOrganizer.exe"),
      ["-p", "Default", "exe", args.title], { detached: !args.wait, stdio: "ignore" });
    if (!args.wait) { child.unref(); return { pid: child.pid, waiting: false, source: "offline_cli" }; }
    const exit = await new Promise<number>(resolve => child.on("exit", code => resolve(code ?? -1)));
    return { exit_code: exit, source: "offline_cli" };
  },
};

registerTool({
  name: "mo2_run_tool", tier: "T3",
  description: "Run a configured customExecutable via MO2 VFS. Live: organizer.start_application. Offline: CLI exe.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), title: z.string(), wait: z.boolean().default(false) }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_run_tool (T3 live start_application + offline CLI fallback)"
```

---

## Task S5.3: `mo2_switch_profile` (T3, cold-restart sequence)

Oracle traps §5.1-5.4. Full sequence: `system.shutdown` → poll PID gone → launch with `-p` → poll `endpoint.json` fresh → sidecar `world.invalidate`.

**Files:** `src/tools/mo2-switch-profile.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_switch_profile",
  async buildPlan(args: { new_profile: string }, ctx) {
    const newProfileDir = join(ctx.config.mo2Root, "profiles", args.new_profile);
    if (!existsSync(newProfileDir)) throw new Error(`profile_not_found: ${args.new_profile}`);
    if (!ctx.config.allowedProfiles.includes(args.new_profile)) throw new Error(`profile_not_allowed: ${args.new_profile}`);
    return {
      diff: `Cold-restart MO2 with -p ${args.new_profile}: shutdown → wait_dead → launch → wait_ready → sidecar_invalidate`,
      affectedFiles: [],
      targets: [],
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    // Step 1: shutdown if running
    if (ctx.pipeClient) {
      const shutdownResp = await ctx.pipeClient.call("system.shutdown", {}, 10000);
      if (!shutdownResp.ok) throw new Error(`shutdown_failed: ${shutdownResp.error?.message}`);
      ctx.pipeClient.close();
    }

    // Step 2: poll PID gone
    const { detectMo2Running } = await import("../detection.js");
    for (let i = 0; i < 30; i++) {
      const det = await detectMo2Running({ mo2Root: ctx.config.mo2Root });
      if (!det.processRunning) break;
      await new Promise(r => setTimeout(r, 1000));
      if (i === 29) throw new Error("mo2_shutdown_timeout_30s");
    }

    // Step 3: launch new
    const { spawn } = await import("node:child_process");
    const child = spawn(join(ctx.config.mo2Root, "ModOrganizer.exe"), ["-p", args.new_profile],
      { detached: true, stdio: "ignore" });
    child.unref();

    // Step 4: poll endpoint.json fresh
    const endpointPath = join(ctx.config.mo2Root, "plugins", "Mo2AgentControl", "bootstrap", "runtime", "endpoint.json");
    let newPipe: string | null = null;
    for (let i = 0; i < 60; i++) {
      try {
        const info = JSON.parse(await (await import("node:fs/promises")).readFile(endpointPath, "utf8"));
        const det = await detectMo2Running({ mo2Root: ctx.config.mo2Root });
        if (det.pid === info.mo2Pid) { newPipe = info.endpoint; break; }
      } catch {}
      await new Promise(r => setTimeout(r, 2000));
    }
    if (!newPipe) throw new Error("mo2_ready_timeout_120s");

    // Step 5: reconnect pipe
    const { PipeClient } = await import("../pipe-client.js");
    const newClient = new PipeClient();
    await newClient.discoverAndConnect(ctx.config.mo2Root);
    // Replace ctx.pipeClient (mutation; bootstrap-managed singleton)
    (ctx as any).pipeClient = newClient;

    // Step 6: sidecar invalidate
    if (ctx.sidecar) {
      await ctx.sidecar.call("world.invalidate", { profile_dir: join(ctx.config.mo2Root, "profiles", args.new_profile) });
    }

    return { new_profile: args.new_profile, new_pipe: newPipe };
  },
};

registerTool({
  name: "mo2_switch_profile", tier: "T3",
  description: "Cold-restart MO2 with a different profile. Shutdown → wait_dead → relaunch → wait_ready → sidecar_invalidate. Refuses if profile not in .mo2-mcp.json allowed_profiles.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), new_profile: z.string() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_switch_profile (T3 cold-restart with full ladder)"
```

---

## Task S5.4: `mo2_configure_executable` (T3, MO2-closed write)

Edit `ModOrganizer.ini [customExecutables]` Qt INI array. Refuses if MO2 running (would overwrite on exit). Atomic INI rewrite preserves other sections verbatim.

**Files:** `src/tools/mo2-configure-executable.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_configure_executable",
  async buildPlan(args, ctx) {
    const { detectMo2Running } = await import("../detection.js");
    const det = await detectMo2Running({ mo2Root: ctx.config.mo2Root });
    if (det.processRunning) throw new Error("mo2_running_ini_unsafe: close MO2 first or use mo2_switch_profile then this tool");
    const iniPath = join(ctx.config.mo2Root, "ModOrganizer.ini");
    const ini = await (await import("../mo-ini.js")).readMoIni(iniPath);
    let diff = "";
    if (args.action === "add") {
      const exists = ini.customExecutables.find(e => e.title === args.entry.title);
      if (exists) throw new Error(`title_exists: ${args.entry.title}`);
      diff = `+ ${args.entry.title} → ${args.entry.binary}`;
    } else if (args.action === "edit") {
      const idx = ini.customExecutables.findIndex(e => e.title === args.title);
      if (idx < 0) throw new Error(`title_not_found: ${args.title}`);
      diff = `~ ${args.title}: ${JSON.stringify(args.updates)}`;
    } else {  // remove
      const idx = ini.customExecutables.findIndex(e => e.title === args.title);
      if (idx < 0) throw new Error(`title_not_found: ${args.title}`);
      diff = `- ${args.title}`;
    }
    return { diff, affectedFiles: [iniPath], targets: [{ path: iniPath, kind: "text-file" }] };
  },
  async applyMutation(plan, ctx) {
    const iniPath = join(ctx.config.mo2Root, "ModOrganizer.ini");
    const { readMoIni } = await import("../mo-ini.js");
    const ini = await readMoIni(iniPath);
    let entries = [...ini.customExecutables];
    if (plan.args.action === "add") entries.push(plan.args.entry);
    else if (plan.args.action === "edit") {
      const idx = entries.findIndex(e => e.title === plan.args.title);
      entries[idx] = { ...entries[idx], ...plan.args.updates };
    } else {
      entries = entries.filter(e => e.title !== plan.args.title);
    }
    // Atomic rewrite: preserve other sections verbatim, replace [customExecutables]
    const newSection = ["[customExecutables]", `size=${entries.length}`,
      ...entries.flatMap((e, i) => Object.entries(e).map(([k, v]) => `${i+1}\\${k}=${typeof v === "boolean" ? (v?"true":"false") : v}`))
    ].join("\n");
    const lines = ini.raw.split(/\r?\n/);
    const range = ini.sectionRanges.get("customExecutables");
    let newText: string;
    if (range) {
      newText = [...lines.slice(0, range[0]), ...newSection.split("\n"), ...lines.slice(range[1] + 1)].join("\n");
    } else {
      newText = ini.raw + "\n" + newSection;
    }
    await atomicWriteText(iniPath, newText);
    return { action: plan.args.action, executables_count: entries.length };
  },
};

registerTool({
  name: "mo2_configure_executable", tier: "T3",
  description: "Add/edit/remove a customExecutables entry. Refuses if MO2 running. Atomic INI rewrite preserves other sections.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), action: z.literal("add"),
               entry: z.object({ title: z.string(), binary: z.string(), arguments: z.string().default(""),
                                 workingDirectory: z.string().default(""), steamAppID: z.string().default(""),
                                 ownicon: z.boolean().default(false), hide: z.boolean().default(false) }) }),
    z.object({ mode: z.literal("plan"), action: z.literal("edit"), title: z.string(), updates: z.record(z.any()) }),
    z.object({ mode: z.literal("plan"), action: z.literal("remove"), title: z.string() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_configure_executable (T3 add/edit/remove with MO2-running guard)"
```

---

## Task S5.5: `mo2_create_mod` (T3, empty mod via broker)

Wraps broker `mods.create`. Optional `above` arg targets priority above a named mod.

**Files:** `src/tools/mo2-create-mod.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_create_mod",
  async buildPlan(args: { name: string; above?: string; profile?: string }, ctx) {
    if (!ctx.pipeClient) throw new Error("live_mo2_required_for_create_mod");
    const profile = args.profile ?? "Default";
    let targetPri = 0;
    if (args.above) {
      const { readProfile } = await import("../profile-reader.js");
      const p = await readProfile(join(ctx.config.mo2Root, "profiles", profile));
      const abovePri = p.mods.find(m => m.name === args.above)?.priority;
      if (abovePri == null) throw new Error(`above_mod_not_found: ${args.above}`);
      targetPri = abovePri + 1;
    }
    return {
      diff: `Create empty mod ${args.name}${args.above ? ` above ${args.above} (pri=${targetPri})` : ""}`,
      affectedFiles: [join(ctx.config.mo2Root, "profiles", profile, "modlist.txt")],
      targets: [{ path: join(ctx.config.mo2Root, "profiles", profile, "modlist.txt"), kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    const profile = args.profile ?? "Default";
    let targetPri: number | undefined;
    if (args.above) {
      const { readProfile } = await import("../profile-reader.js");
      const p = await readProfile(join(ctx.config.mo2Root, "profiles", profile));
      targetPri = (p.mods.find(m => m.name === args.above)?.priority ?? 0) + 1;
    }
    const resp = await ctx.pipeClient!.call("mods.create", { name: args.name, priority: targetPri });
    if (!resp.ok) throw new Error(resp.error?.message);
    if (ctx.sidecar) await ctx.sidecar.call("world.invalidate", { profile_dir: join(ctx.config.mo2Root, "profiles", profile) });
    return resp.result;
  },
};

registerTool({
  name: "mo2_create_mod", tier: "T3",
  description: "Create empty mod via broker mods.create. Optional 'above' positions it above a named mod.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), name: z.string(), above: z.string().optional(), profile: z.string().default("Default") }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_create_mod (T3 empty mod with optional above)"
```

---

## Task S5.6: `mo2_create_separator` (T3, _separator naming)

Source-confirmed naming: `<name>_separator`. Optional `color` written to meta.ini (no public setter — librarian-alpha §A2).

**Files:** `src/tools/mo2-create-separator.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_create_separator",
  async buildPlan(args: { name: string; above?: string; color?: string; profile?: string }, ctx) {
    if (!ctx.pipeClient) throw new Error("live_mo2_required");
    const profile = args.profile ?? "Default";
    let targetPri = 0;
    if (args.above) {
      const { readProfile } = await import("../profile-reader.js");
      const p = await readProfile(join(ctx.config.mo2Root, "profiles", profile));
      const abovePri = p.mods.find(m => m.name === args.above)?.priority;
      if (abovePri == null) throw new Error(`above_mod_not_found`);
      targetPri = abovePri + 1;
    }
    const sepName = `${args.name}_separator`;
    return {
      diff: `Create separator "${args.name}" → ${sepName}${args.color ? ` color=${args.color}` : ""}`,
      affectedFiles: [join(ctx.config.mo2Root, "profiles", profile, "modlist.txt")],
      targets: [{ path: join(ctx.config.mo2Root, "profiles", profile, "modlist.txt"), kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    const sepName = `${args.name}_separator`;
    const profile = args.profile ?? "Default";
    let targetPri: number | undefined;
    if (args.above) {
      const { readProfile } = await import("../profile-reader.js");
      const p = await readProfile(join(ctx.config.mo2Root, "profiles", profile));
      targetPri = (p.mods.find(m => m.name === args.above)?.priority ?? 0) + 1;
    }
    const resp = await ctx.pipeClient!.call("mods.create", { name: sepName, priority: targetPri });
    if (!resp.ok) throw new Error(resp.error?.message);
    // Optional color: write to meta.ini directly (no mobase setter)
    if (args.color) {
      const ini = await (await import("../mo-ini.js")).readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
      const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
      const metaPath = join(modsDir, sepName, "meta.ini");
      await atomicWriteText(metaPath, `[General]\ncolor=${args.color}\n`);
      await ctx.pipeClient!.call("organizer.refresh", { save_changes: false });
    }
    if (ctx.sidecar) await ctx.sidecar.call("world.invalidate", { profile_dir: join(ctx.config.mo2Root, "profiles", profile) });
    return { separator_name: sepName, color_set: !!args.color };
  },
};

registerTool({
  name: "mo2_create_separator", tier: "T3",
  description: "Create a separator (_separator suffix triggers FLAG_SEPARATOR). Optional color written to meta.ini.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), name: z.string(), above: z.string().optional(),
               color: z.string().optional(), profile: z.string().default("Default") }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_create_separator (T3 _separator + optional color)"
```

---

## Task S5.7: `mo2_rename_mod` (T3, cross-profile sync)

Spec: librarian-alpha §A4. `Profile::renameModInAllProfiles` updates every profile's modlist.txt. MCP must scan all profiles in plan.

**Files:** `src/tools/mo2-rename-mod.ts`

- [ ] **Steps 1-3:**

```typescript
const handler: PlanApplyHandler = {
  toolName: "mo2_rename_mod",
  async buildPlan(args: { old_name: string; new_name: string }, ctx) {
    const { readdir, readFile } = await import("node:fs/promises");
    const profilesRoot = join(ctx.config.mo2Root, "profiles");
    const allProfiles = await readdir(profilesRoot);
    const affected: string[] = [];
    const targets: Array<{ path: string; kind: "text-file" | "directory" }> = [];
    for (const prof of allProfiles) {
      const ml = join(profilesRoot, prof, "modlist.txt");
      try {
        const text = await readFile(ml, "utf8");
        if (text.split("\n").some(l => l.replace(/^[+\-]/, "") === args.old_name)) {
          affected.push(ml);
          targets.push({ path: ml, kind: "text-file" });
        }
      } catch {}
    }
    // Also: mod dir itself
    const ini = await (await import("../mo-ini.js")).readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    targets.push({ path: join(modsDir, args.old_name), kind: "directory" });
    return {
      diff: `Rename ${args.old_name} → ${args.new_name} across ${affected.length} profiles + mod dir`,
      affectedFiles: [...affected, join(modsDir, args.new_name)], targets,
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    if (ctx.pipeClient) {
      const resp = await ctx.pipeClient.call("mods.rename", { old_name: args.old_name, new_name: args.new_name });
      if (!resp.ok) throw new Error(resp.error?.message);
      if (ctx.sidecar) await ctx.sidecar.call("world.invalidate", { profile_dir: join(ctx.config.mo2Root, "profiles", "Default") });
      return resp.result;
    }
    // Offline: rename dir + rewrite every profile's modlist.txt
    const ini = await (await import("../mo-ini.js")).readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    const { rename, readdir, readFile } = await import("node:fs/promises");
    await rename(join(modsDir, args.old_name), join(modsDir, args.new_name));
    const profilesRoot = join(ctx.config.mo2Root, "profiles");
    const allProfiles = await readdir(profilesRoot);
    const updated: string[] = [];
    for (const prof of allProfiles) {
      const ml = join(profilesRoot, prof, "modlist.txt");
      try {
        let text = await readFile(ml, "utf8");
        const lines = text.split(/\r?\n/).map(l => {
          const m = l.match(/^([+\-])(.+)$/);
          if (m && m[2] === args.old_name) return `${m[1]}${args.new_name}`;
          return l;
        });
        const newText = lines.join("\n");
        if (newText !== text) { await atomicWriteText(ml, newText); updated.push(prof); }
      } catch {}
    }
    return { renamed_dir: true, profiles_updated: updated };
  },
};

registerTool({
  name: "mo2_rename_mod", tier: "T3",
  description: "Rename mod across ALL profiles + mod folder. Live: broker mods.rename. Offline: fs rename + per-profile modlist.txt rewrite.",
  inputSchema: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), old_name: z.string(), new_name: z.string() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
  ]),
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx),
});
```

- [ ] **Steps 4-5:**

```bash
git commit -am "feat(mo2-mcp): mo2_rename_mod (T3 cross-profile sync + dir rename)"
```

---

## End of S5a

7 tasks land: `mo2_install` (FOMOD), `mo2_run_tool`, `mo2_switch_profile`, `mo2_configure_executable`, `mo2_create_mod`, `mo2_create_separator`, `mo2_rename_mod`. ~7 commits.

**Tool count after S5a:** 22 (S4) + 7 (S5a) = **29 tools**.

Continue in `2026-06-14-mo2-mcp-S5b-mod-ops-and-profile-lifecycle.md`:
- S5.8 mo2_reinstall_mod
- S5.9 mo2_remove_mod (default backup_first=true)
- S5.10 mo2_set_file_hidden (.mohidden)
- S5.11 mo2_create_profile
- S5.12 mo2_clone_profile
- S5.13 mo2_rename_profile
- S5.14 final v1 acceptance gate against `B:\WastelandBlues 2.0`
