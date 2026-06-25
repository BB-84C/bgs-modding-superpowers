/**
 * mo2_install — T3 install mod via FOMOD Pattern A (S5a Task S5.1).
 *
 * Plan steps (computed up front):
 * 1. Try sidecar fomod.parse_choices to detect FOMOD
 * 2. If FOMOD without choices → throw fomod_choices_required (carries tree)
 * 3. Compute target mods/<mod_name>; reject if exists
 * 4. Compute affected files = [dest_path, modlist.txt]
 *
 * Apply steps:
 * 1. Stage to <MO2_Root>/.mo2-mcp/staging/<install_id>/ via sidecar
 *    (install.stage_fomod for FOMOD, archive.extract_all for simple)
 * 2. Create empty mod via broker installation.create_mod_from_directory
 *    (or mkdir if offline)
 * 3. rename staging → mods/<name>
 * 4. Write meta.ini (oracle §4.3 fields: gameName, installationFile, etc.)
 * 5. Register in modlist.txt at top or bottom
 * 6. organizer.refresh + world.invalidate
 */
import { z } from "zod";
import { readFile, mkdir, rename, cp, readdir, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, basename, extname, dirname } from "node:path";
import { randomUUID } from "node:crypto";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { atomicWriteText } from "../atomic.js";
import { resolveModsDir, resolveProfileDir } from "../path-helpers.js";
import { readMoIni, resolveGameName } from "../mo-ini.js";
import { assertActiveProfile } from "../profile-guard.js";
import { invalidateWorld } from "./state-sync.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";
import { detectFomod, hasFomodChoices } from "../fomod-helpers.js";
import { FomodChoicesRequiredError, type FomodTreeShape } from "../fomod-required-error.js";
import { gatherMo2FomodState } from "../mo2-state-for-fomod.js";

// BUG-10 fix (2026-06-17): FOMOD page/group/option names + archive_path +
// mod_name + plan_id + lease_token all gain .min(1). Empty strings in any of
// these fall through to internal "<thing> not found" handler errors today;
// rejecting them at the Zod layer surfaces invalid_arguments instead.
const FomodChoiceSchema = z.object({
  page_name: z.string().min(1),
  selected_options: z.array(
    z.object({ group_name: z.string().min(1), option_name: z.string().min(1) }),
  ),
});

const inputSchema = z.discriminatedUnion("mode", [
  z.object({
    mode: z.literal("plan"),
    archive_path: z.string().min(1),
    mod_name: z.string().min(1),
    profile: z.string().default("Default"),
    target_priority: z.union([z.literal("top"), z.literal("bottom"), z.number().int()]).default("bottom"),
    fomod_choices: z.array(FomodChoiceSchema).optional(),
    nexus_mod_id: z.number().int().optional(),
    version: z.string().optional(),
    category: z.string().optional(),
  }),
  z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);

async function _copyDirectoryContents(sourceDir: string, destDir: string): Promise<void> {
  await mkdir(destDir, { recursive: true });
  const entries = await readdir(sourceDir, { withFileTypes: true });
  for (const entry of entries) {
    await cp(join(sourceDir, entry.name), join(destDir, entry.name), { recursive: true });
  }
}

// BUG-14 BUG-D (issue #14): BGS mod archives commonly wrap content in a
// top-level `Data/` directory (per BGS convention), or a `<modname>/`
// wrapper, or both. MO2's GUI installer flattens these so the plugin
// lands at `mods/<modname>/<plugin>.esm`, not at
// `mods/<modname>/Data/<plugin>.esm`. Without flattening, MO2's VFS
// projects the file as `<game>/Data/Data/<plugin>.esm` and the engine
// silently cannot find it.
//
// Heuristic, in priority order:
//  1. Plugin file (.esm/.esp/.esl) at this level → this is the mod root.
//  2. Known BGS asset directory (meshes, textures, scripts, fomod, sfse,
//     f4se, skse, etc.) at this level → mod root (asset-only mods are
//     valid; no plugin required).
//  3. Single subdirectory and no hits at this level → recurse into it
//     (handles the common Data/ and ModName/Data/ wrappers).
//  4. Anything else (multiple subdirs without plugins or asset markers)
//     → ambiguous, leave layout as-is.
//
// Depth is capped at 4 to avoid pathological extracts. The original
// staging dir itself is never removed (it's the destination).
const _PLUGIN_EXTS = new Set([".esm", ".esp", ".esl"]);
const _BGS_ASSET_DIRS = new Set([
  // BGS-standard
  "meshes",
  "textures",
  "sound",
  "music",
  "materials",
  "scripts",
  "interface",
  "seq",
  "video",
  "lodsettings",
  "shadersfx",
  "strings",
  // Installer & xSE
  "fomod",
  "f4se",
  "skse",
  "skse64",
  "sfse",
  "obse",
  "fose",
  "nvse",
  // Misc engine roots that show up in real archives
  "platform",
  "menus",
]);

async function _findBgsModRoot(dir: string, depth: number, maxDepth = 4): Promise<string | null> {
  if (depth > maxDepth) return null;
  let entries: import("node:fs").Dirent[];
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return null;
  }
  for (const entry of entries) {
    if (entry.isFile() && _PLUGIN_EXTS.has(extname(entry.name).toLowerCase())) {
      return dir;
    }
  }
  for (const entry of entries) {
    if (entry.isDirectory() && _BGS_ASSET_DIRS.has(entry.name.toLowerCase())) {
      return dir;
    }
  }
  const subdirs = entries.filter((e) => e.isDirectory());
  if (subdirs.length === 1) {
    return _findBgsModRoot(join(dir, subdirs[0].name), depth + 1, maxDepth);
  }
  return null;
}

async function _flattenBgsArchive(stagingDir: string): Promise<{ flattened: boolean; from?: string }> {
  const root = await _findBgsModRoot(stagingDir, 0);
  if (!root || root === stagingDir) return { flattened: false };
  // Move root's entries up to stagingDir, then clean the now-empty
  // intermediate directories. Two-pass: first read, then rename.
  const rootEntries = await readdir(root);
  for (const name of rootEntries) {
    await rename(join(root, name), join(stagingDir, name));
  }
  // Walk the chain from `root` back up to stagingDir's child and rm each
  // emptied dir. dirname() loop stops once we reach stagingDir.
  let cleanup: string | null = root;
  while (cleanup && cleanup !== stagingDir) {
    try {
      await rm(cleanup, { recursive: true, force: true });
    } catch {
      break;
    }
    const parent = dirname(cleanup);
    if (parent === cleanup) break;
    cleanup = parent === stagingDir ? null : parent;
  }
  return { flattened: true, from: root };
}

// BUG-14 BUG-E (issue #14): enumerate plugin files at the final mod root
// and register them in the profile's plugins.txt. Without this, every
// install completed "successfully" but the mod's plugins stayed inactive
// — the agent had to do a separate enumeration + N×toggle_plugin calls
// to actually activate them.
//
// Behavior matches MO2 GUI's "Install Mod from Archive": newly-installed
// plugins land enabled (asterisk prefix in plugins.txt per FO4/SSE
// convention). Existing entries (case-insensitive match) are preserved
// — we never overwrite a disabled plugin's state.
async function _registerPluginsInPluginsTxt(
  modRoot: string,
  pluginsTxtPath: string,
): Promise<string[]> {
  let modEntries: import("node:fs").Dirent[];
  try {
    modEntries = await readdir(modRoot, { withFileTypes: true });
  } catch {
    return [];
  }
  const newPlugins = modEntries
    .filter((e) => e.isFile() && _PLUGIN_EXTS.has(extname(e.name).toLowerCase()))
    .map((e) => e.name)
    .sort();
  if (newPlugins.length === 0) return [];

  const existingTxt = await readFile(pluginsTxtPath, "utf8").catch(() => "");
  const existingLower = new Set(
    existingTxt
      .split(/\r?\n/)
      .filter((line) => line.length > 0 && !line.startsWith("#"))
      .map((line) => line.replace(/^\*/, "").trim().toLowerCase()),
  );

  const linesToAdd: string[] = [];
  const registered: string[] = [];
  for (const plugin of newPlugins) {
    if (!existingLower.has(plugin.toLowerCase())) {
      linesToAdd.push(`*${plugin}`);
      registered.push(plugin);
    }
  }
  if (linesToAdd.length === 0) return [];

  const sep = existingTxt.length === 0 || existingTxt.endsWith("\n") ? "" : "\n";
  const newTxt = `${existingTxt}${sep}${linesToAdd.join("\n")}\n`;
  await atomicWriteText(pluginsTxtPath, newTxt);
  return registered;
}

// FOMOD detection + choices-shape helpers were extracted into
// ../fomod-helpers.ts (2026-06-17 v1.2 Batch 4 Lane 4C) so mo2_reinstall_mod
// can share the same contract with the sidecar instead of carrying a parallel
// regex / shape that drifts. See fomod-helpers.ts for the not_a_fomod/info.xml
// substring contract and the empty-array=no-choices semantics (BUG-19 fix).

const handler: PlanApplyHandler = {
  toolName: "mo2_install",
  async buildPlan(args, ctx) {
    const bound = requireBoundContext(ctx);
    if (!bound.sidecar) {
      throw new Error("sidecar_required_for_install");
    }
    const archivePath = args.archive_path as string;
    const modName = args.mod_name as string;
    const profile = (args.profile as string) ?? "Default";
    // BUG-9 fix (2026-06-17): refuse plan generation when MO2 is live on a
    // different profile (the modlist.txt that will be registered into
    // belongs to <profile>). assertActiveProfile is a no-op when MO2 is
    // offline (pipeClient absent).
    await assertActiveProfile(ctx, profile);
    const modsDir = await resolveModsDir(ctx);
    const destPath = join(modsDir, modName);
    if (existsSync(destPath)) {
      throw new Error(`mod_name_exists: ${modName}`);
    }

    // Detect FOMOD via shared helper (delegates to sidecar.fomod.parse_choices).
    // Lane V3 FOMOD-EXT: gather MO2 state so the sidecar can evaluate
    // <moduleDependencies>, <visible>, and <dependencyType> against the real
    // load order; the fomod_tree surfaced in fomod_choices_required will carry
    // dependencies_status fields agents can introspect before picking choices.
    const mo2State = await gatherMo2FomodState(ctx, profile);
    const { isFomod, tree: fomodTree } = await detectFomod(
      bound.sidecar,
      archivePath,
      mo2State as unknown as Record<string, unknown>,
    );

    if (isFomod && !hasFomodChoices(args)) {
      throw new FomodChoicesRequiredError({
        code: "fomod_choices_required",
        message: "fomod_choices_required",
        fomod_tree: fomodTree as FomodTreeShape,
      });
    }

    const profileDir = resolveProfileDir(ctx, profile);
    const modlistPath = join(profileDir, "modlist.txt");
    // BUG-14 BUG-E (issue #14): track plugins.txt as an affected file so
    // the snapshot taken at apply time captures its pre-write state and
    // rollback can restore it. Lease target as well so concurrent installs
    // detect plugins.txt drift between plan and apply.
    const pluginsTxtPath = join(profileDir, "plugins.txt");

    return {
      diff: `Install ${modName} (FOMOD=${isFomod}, target_priority=${String(args.target_priority)})`,
      affectedFiles: [destPath, modlistPath, pluginsTxtPath],
      targets: [
        { path: modlistPath, kind: "text-file" },
        { path: pluginsTxtPath, kind: "text-file" },
      ],
    };
  },

  async applyMutation(plan, ctx) {
    const args = plan.args;
    const archivePath = args.archive_path as string;
    const modName = args.mod_name as string;
    const profile = (args.profile as string) ?? "Default";
    const modsDir = await resolveModsDir(ctx);
    const destPath = join(modsDir, modName);
    const installId = randomUUID();
    const bound = requireBoundContext(ctx);
    const stagingDir = join(bound.config.mo2Root, ".mo2-mcp", "staging", installId);

    if (!bound.sidecar) throw new Error("sidecar_required");
    await assertActiveProfile(ctx, profile);

    // 1. Stage content into stagingDir.
    const useFomodChoices = hasFomodChoices(args);
    if (useFomodChoices) {
      // Lane V3: forward MO2 state so pyfomod's Installer enforces
      // <gameDependency> / <fileDependency> checks during the wizard walk.
      // A picked option whose preconditions don't hold raises invalid_choices.
      const mo2State = await gatherMo2FomodState(ctx, profile);
      await bound.sidecar.call("install.stage_fomod", {
        archive_path: archivePath,
        choices: args.fomod_choices,
        staging_dir: stagingDir,
        mo2_state: mo2State,
      });
    } else {
      await bound.sidecar.call("archive.extract_all", {
        archive_path: archivePath,
        dest: stagingDir,
      });
      // BUG-14 BUG-D: flatten common BGS archive wrapper patterns
      // (Data/, ModName/, ModName/Data/) so the plugin and assets land
      // at the mod folder root, not inside a Data/ subdir that MO2's
      // VFS would double-prefix. FOMOD-staged installs already map
      // source→destination explicitly so they don't need this pass.
      await _flattenBgsArchive(stagingDir);
    }

    // 2. Live broker createMod creates the destination directory itself; copy
    // staged contents into that broker-returned path. Offline path owns the
    // destination directory creation and keeps the clobber guard before rename.
    let finalDestPath = destPath;
    if (bound.pipeClient) {
      const resp = await bound.pipeClient.call("installation.create_mod_from_directory", {
        name: modName,
        source_dir: stagingDir,
      });
      if (!resp.ok) throw new Error(resp.error?.message ?? "broker error");
      const result = resp.result as { absolute_path?: unknown } | undefined;
      finalDestPath = typeof result?.absolute_path === "string" ? result.absolute_path : destPath;
      await _copyDirectoryContents(stagingDir, finalDestPath);
      await rm(stagingDir, { recursive: true, force: true });
    } else {
      await mkdir(modsDir, { recursive: true });
      if (existsSync(destPath)) {
        throw new Error(`mod_name_exists: ${modName}`);
      }
      try {
        await rename(stagingDir, destPath);
      } catch (e) {
        if (e instanceof Error && "code" in e && (e as NodeJS.ErrnoException).code === "EXDEV") {
          // Cross-volume: fallback to copy.
          await cp(stagingDir, destPath, { recursive: true });
        } else {
          throw e;
        }
      }
      finalDestPath = destPath;
    }

    if (!existsSync(finalDestPath)) {
      throw new Error(`mod_destination_missing: ${finalDestPath}`);
    }

    // 3. Write meta.ini (oracle §4.3 fields).
    const ini = await readMoIni(join(bound.config.mo2Root, "ModOrganizer.ini"));
    // meta.ini's `gameName=` field expects the TitleCase display name
    // (e.g. "Starfield", "Fallout4", "SkyrimSE"), not the lowercase internal
    // key. Use resolveGameName which prefers `gameName=` directly and falls
    // back to reverse-mapping `game=` (older MO2).
    const meta = [
      "[General]",
      `gameName=${resolveGameName(ini.general)}`,
      `modid=${args.nexus_mod_id ?? 0}`,
      `version=${args.version ?? ""}`,
      `installationFile=${basename(archivePath)}`,
      "nexusFileStatus=1",
      "repository=Nexus",
      `category="${args.category ?? 0}"`,
      "notes=\"\"",
      "validated=true",
    ].join("\n");
    await atomicWriteText(join(finalDestPath, "meta.ini"), meta + "\n");

    // 4. Register in modlist.txt.
    const profileDir = resolveProfileDir(ctx, profile);
    const modlistPath = join(profileDir, "modlist.txt");
    const existing = await readFile(modlistPath, "utf8").catch(() => "");
    const newLine = `+${modName}`;
    const lines = existing.length === 0 ? [] : existing.split(/\r?\n/).filter((line) => line.length > 0);
    if (!lines.includes(newLine)) {
      const updated = args.target_priority === "top"
        ? `${newLine}\n${existing}`
        : `${existing}${existing.endsWith("\n") || existing.length === 0 ? "" : "\n"}${newLine}\n`;
      await atomicWriteText(modlistPath, updated);
    }

    // 5. BUG-14 BUG-E: register fresh-install plugins in plugins.txt.
    // Before this fix, every mo2_install completed "successfully" but
    // the mod's plugins stayed inactive — the agent had to do a separate
    // enumeration + N×toggle_plugin calls to actually activate them.
    const pluginsTxtPath = join(profileDir, "plugins.txt");
    const pluginsRegistered = await _registerPluginsInPluginsTxt(finalDestPath, pluginsTxtPath);

    // 6. If live broker is up, ask MO2 to re-scan so the freshly-written
    // plugins.txt rows become active in MO2's in-memory plugin list.
    // Best-effort: ignore failures (the file write already took, and
    // MO2 will see it on next user-driven refresh either way).
    if (pluginsRegistered.length > 0 && bound.pipeClient) {
      try {
        await bound.pipeClient.call("organizer.refresh", { save_changes: false });
      } catch {
        // swallowed: see comment above
      }
    }

    // 7. Invalidate sidecar World cache so subsequent asset reads see the new mod.
    await invalidateWorld(ctx, [profile]);

    return {
      mod_name: modName,
      dest_path: finalDestPath,
      fomod_used: useFomodChoices,
      installation_file: basename(archivePath),
      plugins_registered: pluginsRegistered,
    };
  },
};

registerTool({
  name: "mo2_install",
  tier: "T3",
  description:
    "Install mod from archive (.zip/.7z/.rar). FOMOD non-interactive via fomod_choices. Pattern A: sidecar parse/extract → broker createMod → move → meta.ini → register modlist.txt.",
  inputSchema,
  handler: (args, ctx) =>
    routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
