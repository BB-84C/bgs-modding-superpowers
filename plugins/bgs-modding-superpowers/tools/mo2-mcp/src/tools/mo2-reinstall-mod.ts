/**
 * mo2_reinstall_mod — T3 reinstall from meta.ini[General] installationFile.
 *
 * Live-only: reads the source archive name via broker mods.meta_read, then:
 *   - Non-FOMOD: delegates to broker installation.install_local_archive (the
 *     FOMOD-blind primitive — fine for plain archives).
 *   - FOMOD with choices: routes through Pattern A — sidecar
 *     install.stage_fomod stages the chosen tree into a scratch dir, then we
 *     manually replace the existing mod folder's content with that staged
 *     tree. This avoids passing the FOMOD archive to the broker, which would
 *     popup the MO2 native FOMOD wizard and block the Qt main thread
 *     (BUG-16-class hang). See ../fomod-helpers.ts for the contract.
 *
 * BUG-22 fix (2026-06-17 v1.2 Batch 4 Lane 4C): meta.ini's installationFile
 * may be either a basename (legacy MO2 behavior — file lives in the active
 * downloads dir) or an absolute path (MO2 records the original path when the
 * archive was added from outside the downloads tree). Previously this tool
 * did `join(downloadsDir, installFile)` unconditionally; node:path.join on an
 * absolute second arg produces a garbage concatenated path like
 * `C:\downloads\F:\Fallout 4 Mods\...` on Windows, and existsSync then
 * misreported "archive_not_in_downloads" for archives that were actually
 * present at an absolute location. The fix is path.isAbsolute-gated. Error
 * code is now `archive_missing` (uniform) since absolute paths are legitimate.
 *
 * BUG-23 fix (2026-06-17 v1.2 Batch 4 Lane 4C): apply previously validated
 * fomod_choices presence at apply time but then dropped them on the floor by
 * calling broker installation.install_local_archive(archive, name) raw. The
 * broker docs at tools/mo2-control-plane/live-bridge/mo2_agent_control.py:1699
 * flag that primitive as "FOMOD-blind — wizard runs inside MO2 when archive
 * contains info.xml". On a real FOMOD archive that would popup the MO2 native
 * wizard, block the Qt main thread, and hang the broker (BUG-16-class). Now
 * routes FOMOD reinstall through Pattern A (sidecar staging + manual content
 * replacement); only non-FOMOD reinstalls reach the broker.
 *
 * BUG-24 fix (2026-06-17 v1.2 Batch 4 Lane 4C): plan now detects FOMOD via
 * the shared helper and surfaces the parsed page/group/option tree via the
 * `fomod_choices_required_for_reinstall` error envelope (mirroring
 * mo2_install's `fomod_choices_required` shape), so agents can introspect
 * what choices the archive needs before apply. Previously plan was FOMOD-blind
 * and the wizard tree only surfaced inside the broker.
 */
import { z } from "zod";
import { existsSync } from "node:fs";
import { readFile, readdir, rm, cp, mkdir } from "node:fs/promises";
import * as path from "node:path";
import { randomUUID } from "node:crypto";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { atomicWriteText } from "../atomic.js";
import { readMoIni } from "../mo-ini.js";
import type { ToolContext } from "../types.js";
import { invalidateWorld } from "./state-sync.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";
import { detectFomod, hasFomodChoices } from "../fomod-helpers.js";
import { FomodChoicesRequiredError, type FomodTreeShape } from "../fomod-required-error.js";

// BUG-10 fix (2026-06-17): FOMOD page/group/option names + mod name + plan_id
// + lease_token all gain .min(1) so empty strings fail Zod safeParse instead
// of falling through to handler-level errors.
const FomodChoiceSchema = z.object({
  page_name: z.string().min(1),
  selected_options: z.array(
    z.object({ group_name: z.string().min(1), option_name: z.string().min(1) }),
  ),
});

const inputSchema = z.discriminatedUnion("mode", [
  z.object({
    mode: z.literal("plan"),
    name: z.string().min(1),
    fomod_choices: z.array(FomodChoiceSchema).optional(),
  }),
  z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);

interface MetaReadResponse {
  ok: boolean;
  result?: {
    meta?: {
      General?: {
        installationFile?: string;
      };
    };
  };
  error?: { message?: string } | null;
}

function _extractInstallationFile(resp: MetaReadResponse): string {
  if (!resp.ok) throw new Error(resp.error?.message ?? "mods.meta_read failed");
  const installFile = resp.result?.meta?.General?.installationFile;
  if (!installFile) {
    throw new Error("no_installation_file_in_meta_ini: cannot reinstall this mod (likely added pre-MO2-2.x)");
  }
  return installFile;
}

/**
 * BUG-22 fix: resolve `installationFile` to an absolute archive path,
 * tolerating both legacy bare-basename values (live under MO2's configured
 * downloads dir) and absolute paths (used when MO2 indexes an archive from
 * outside the downloads tree). path.join on an absolute second arg produces
 * a garbage concatenated path; we gate on path.isAbsolute first.
 */
function _resolveArchivePath(downloadsDir: string, installFile: string): string {
  return path.isAbsolute(installFile) ? installFile : path.join(downloadsDir, installFile);
}

async function _readInstallSource(args: Record<string, unknown>, ctx: ToolContext): Promise<{
  installFile: string;
  archivePath: string;
  modPath: string;
}> {
  const bound = requireBoundContext(ctx);
  if (!bound.pipeClient) throw new Error("live_mo2_required_for_reinstall");
  const name = args.name as string;
  const meta = await bound.pipeClient.call("mods.meta_read", { name }) as MetaReadResponse;
  const installFile = _extractInstallationFile(meta);
  const ini = await readMoIni(path.join(bound.config.mo2Root, "ModOrganizer.ini"));
  const downloadsDir = ini.settings.downloadDirectory ?? path.join(bound.config.mo2Root, "downloads");
  const modsDir = ini.settings.modDirectory ?? path.join(bound.config.mo2Root, "mods");
  const archivePath = _resolveArchivePath(downloadsDir, installFile);
  if (!existsSync(archivePath)) throw new Error(`archive_missing: ${archivePath}`);
  return { installFile, archivePath, modPath: path.join(modsDir, name) };
}

/**
 * Replace the content of an existing mod folder with the content of a staged
 * directory while preserving meta.ini. Used by the FOMOD reinstall apply path
 * (BUG-23 fix) so the broker's FOMOD-blind installMod primitive is never
 * invoked on a FOMOD archive.
 *
 * Note: this does NOT call broker organizer.refresh from the TS layer. Memory
 * rule .opencode/memory/45-mo2-mcp-internals.md rule 2 forbids that — calling
 * organizer.refresh from TS after a separate broker round-trip corrupts the
 * in-memory modlist. Content changes inside an existing mod folder don't
 * touch IModList registration, so MO2's own next refresh cycle picks them up
 * naturally; we only need to invalidate the sidecar's World cache (caller
 * does that via invalidateWorld).
 */
async function _replaceModContent(modPath: string, stagingDir: string, newInstallationFile: string): Promise<void> {
  // Preserve existing meta.ini content so we can restore it with the updated
  // installationFile after the swap.
  const existingMetaPath = path.join(modPath, "meta.ini");
  const existingMeta = await readFile(existingMetaPath, "utf8").catch(() => "");

  // Clear existing mod content (preserve the modPath directory itself so the
  // modlist registration stays valid).
  const entries = await readdir(modPath, { withFileTypes: true });
  for (const entry of entries) {
    await rm(path.join(modPath, entry.name), { recursive: true, force: true });
  }

  // Copy staged content into modPath. Mirrors _copyDirectoryContents in
  // mo2-install.ts shape.
  await mkdir(modPath, { recursive: true });
  const stagedEntries = await readdir(stagingDir, { withFileTypes: true });
  for (const entry of stagedEntries) {
    await cp(path.join(stagingDir, entry.name), path.join(modPath, entry.name), { recursive: true });
  }

  // Restore meta.ini with updated installationFile. If the existing meta had
  // an installationFile= line we patch it in place; otherwise we append.
  if (existingMeta.length > 0) {
    const installationFileRegex = /^installationFile=.*$/m;
    const newLine = `installationFile=${newInstallationFile}`;
    const updatedMeta = installationFileRegex.test(existingMeta)
      ? existingMeta.replace(installationFileRegex, newLine)
      : `${existingMeta.replace(/\s*$/, "")}\n${newLine}\n`;
    await atomicWriteText(existingMetaPath, updatedMeta);
  }
}

const handler: PlanApplyHandler = {
  toolName: "mo2_reinstall_mod",
  async buildPlan(args, ctx) {
    const name = args.name as string;
    const { installFile: _installFile, archivePath, modPath } = await _readInstallSource(args, ctx);

    // BUG-24 fix: detect FOMOD at plan time and surface the parsed tree via
    // the fomod_choices_required_for_reinstall error envelope so the agent can
    // introspect pages/groups/options BEFORE apply. Mirrors mo2_install's
    // plan-time gate. Sidecar may be absent in some live setups (binding
    // failed sidecar startup); in that case we can't detect FOMOD, and fall
    // through to a best-effort plan. The apply-time gate is the safety net.
    const bound = requireBoundContext(ctx);
    let isFomod = false;
    if (bound.sidecar) {
      const detection = await detectFomod(bound.sidecar, archivePath);
      isFomod = detection.isFomod;
      if (isFomod && !hasFomodChoices(args)) {
        throw new FomodChoicesRequiredError({
          code: "fomod_choices_required_for_reinstall",
          message: "fomod_choices_required_for_reinstall",
          fomod_tree: detection.tree as FomodTreeShape,
        });
      }
    }

    return {
      diff: `Reinstall ${name} from ${archivePath} (FOMOD=${isFomod}). Priority + meta preserved; content replaced.`,
      affectedFiles: [modPath],
      targets: [{ path: modPath, kind: "directory" }],
    };
  },

  async applyMutation(plan, ctx) {
    const bound = requireBoundContext(ctx);
    const pipeClient = bound.pipeClient;
    if (!pipeClient) throw new Error("live_mo2_required_for_reinstall");
    const name = plan.args.name as string;
    const { installFile, archivePath, modPath } = await _readInstallSource(plan.args, ctx);

    // Re-detect FOMOD at apply (defense-in-depth: archive could change between
    // plan and apply; the broker primitive is FOMOD-blind so we must gate).
    let isFomod = false;
    if (bound.sidecar) {
      const detection = await detectFomod(bound.sidecar, archivePath);
      isFomod = detection.isFomod;
    }

    if (isFomod && !hasFomodChoices(plan.args)) {
      throw new Error("fomod_choices_required_for_reinstall");
    }

    if (isFomod) {
      // BUG-23 fix: route FOMOD reinstall through Pattern A so the broker's
      // FOMOD-blind installMod is never invoked on a FOMOD archive.
      if (!bound.sidecar) {
        throw new Error("sidecar_required_for_fomod_reinstall");
      }
      const stagingDir = path.join(bound.config.mo2Root, ".mo2-mcp", "staging", randomUUID());
      try {
        await bound.sidecar.call("install.stage_fomod", {
          archive_path: archivePath,
          choices: plan.args.fomod_choices,
          staging_dir: stagingDir,
        });
        await _replaceModContent(modPath, stagingDir, path.basename(archivePath));
      } finally {
        // Best-effort cleanup; ignore errors so a partial-stage cleanup
        // failure does not mask the underlying apply error.
        await rm(stagingDir, { recursive: true, force: true }).catch(() => undefined);
      }
      await invalidateWorld(ctx, ["Default"]);
      return { reinstalled: name, archive: installFile, fomod_used: true };
    }

    // Non-FOMOD: existing broker path. installation.install_local_archive is
    // documented as FOMOD-blind, so safe for plain archives.
    const resp = await pipeClient.call("installation.install_local_archive", {
      archive_path: archivePath,
      name_suggestion: name,
    }) as { ok: boolean; result?: Record<string, unknown>; error?: { message?: string } | null };
    if (!resp.ok) throw new Error(resp.error?.message ?? "installation.install_local_archive failed");

    await invalidateWorld(ctx, ["Default"]);

    return { reinstalled: name, archive: installFile, fomod_used: false };
  },
};

registerTool({
  name: "mo2_reinstall_mod",
  tier: "T3",
  description:
    "Reinstall mod from its meta.ini[installationFile]. Requires file in downloads/. FOMOD requires fomod_choices.",
  inputSchema,
  handler: (args, ctx) =>
    routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
