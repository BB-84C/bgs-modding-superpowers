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
import { readFile, mkdir, rename, cp } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, basename } from "node:path";
import { randomUUID } from "node:crypto";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { atomicWriteText } from "../atomic.js";
import { resolveModsDir, resolveProfileDir } from "../path-helpers.js";
import { readMoIni } from "../mo-ini.js";

const FomodChoiceSchema = z.object({
  page_name: z.string(),
  selected_options: z.array(
    z.object({ group_name: z.string(), option_name: z.string() }),
  ),
});

const inputSchema = z.discriminatedUnion("mode", [
  z.object({
    mode: z.literal("plan"),
    archive_path: z.string(),
    mod_name: z.string(),
    profile: z.string().default("Default"),
    target_priority: z.union([z.literal("top"), z.literal("bottom"), z.number().int()]).default("bottom"),
    fomod_choices: z.array(FomodChoiceSchema).optional(),
    nexus_mod_id: z.number().int().optional(),
    version: z.string().optional(),
    category: z.string().optional(),
  }),
  z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);

const handler: PlanApplyHandler = {
  toolName: "mo2_install",
  async buildPlan(args, ctx) {
    if (!ctx.sidecar) {
      throw new Error("sidecar_required_for_install");
    }
    const archivePath = args.archive_path as string;
    const modName = args.mod_name as string;
    const profile = (args.profile as string) ?? "Default";
    const modsDir = await resolveModsDir(ctx);
    const destPath = join(modsDir, modName);
    if (existsSync(destPath)) {
      throw new Error(`mod_name_exists: ${modName}`);
    }

    // Detect FOMOD: try sidecar.fomod.parse_choices; non-FOMOD will throw.
    let isFomod = false;
    let fomodTree: unknown = null;
    try {
      fomodTree = await ctx.sidecar.call("fomod.parse_choices", { archive_path: archivePath });
      isFomod = true;
    } catch (e) {
      if (e instanceof Error && !/not_a_fomod|info\.xml/i.test(e.message)) {
        throw e;
      }
    }

    if (isFomod && !args.fomod_choices) {
      const err = new Error("fomod_choices_required");
      (err as Error & { fomod_tree?: unknown }).fomod_tree = fomodTree;
      throw err;
    }

    const profileDir = resolveProfileDir(ctx, profile);
    const modlistPath = join(profileDir, "modlist.txt");

    return {
      diff: `Install ${modName} (FOMOD=${isFomod}, target_priority=${String(args.target_priority)})`,
      affectedFiles: [destPath, modlistPath],
      targets: [{ path: modlistPath, kind: "text-file" }],
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
    const stagingDir = join(ctx.config.mo2Root, ".mo2-mcp", "staging", installId);

    if (!ctx.sidecar) throw new Error("sidecar_required");

    // 1. Stage content into stagingDir.
    if (args.fomod_choices) {
      await ctx.sidecar.call("install.stage_fomod", {
        archive_path: archivePath,
        choices: args.fomod_choices,
        staging_dir: stagingDir,
      });
    } else {
      await ctx.sidecar.call("archive.extract_all", {
        archive_path: archivePath,
        dest: stagingDir,
      });
    }

    // 2. Ask the live broker to create the mod when available, then move
    // staged content into the final mod directory. Offline tests use mkdir.
    if (ctx.pipeClient) {
      const resp = await ctx.pipeClient.call("installation.create_mod_from_directory", {
        name: modName,
        source_dir: stagingDir,
      });
      if (!resp.ok) throw new Error(resp.error?.message ?? "broker error");
    } else {
      await mkdir(modsDir, { recursive: true });
    }

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

    // 3. Write meta.ini (oracle §4.3 fields).
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const meta = [
      "[General]",
      `gameName=${ini.general.game ?? ""}`,
      `modid=${args.nexus_mod_id ?? 0}`,
      `version=${args.version ?? ""}`,
      `installationFile=${basename(archivePath)}`,
      "nexusFileStatus=1",
      "repository=Nexus",
      `category="${args.category ?? 0}"`,
      "notes=\"\"",
      "validated=true",
    ].join("\n");
    await atomicWriteText(join(destPath, "meta.ini"), meta + "\n");

    // 4. Register in modlist.txt.
    const modlistPath = join(resolveProfileDir(ctx, profile), "modlist.txt");
    const existing = await readFile(modlistPath, "utf8").catch(() => "");
    const newLine = `+${modName}`;
    const updated = args.target_priority === "top"
      ? `${newLine}\n${existing}`
      : `${existing}${existing.endsWith("\n") || existing.length === 0 ? "" : "\n"}${newLine}\n`;
    await atomicWriteText(modlistPath, updated);

    // 5. Optional refresh + invalidate.
    if (ctx.pipeClient) {
      await ctx.pipeClient.call("organizer.refresh", { save_changes: true }).catch(() => {});
    }
    await ctx.sidecar.call("world.invalidate", {
      profile_dir: resolveProfileDir(ctx, profile),
    }).catch(() => {});

    return {
      mod_name: modName,
      dest_path: destPath,
      fomod_used: !!args.fomod_choices,
      installation_file: basename(archivePath),
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
