/**
 * mo2_reinstall_mod — T3 reinstall from meta.ini[General] installationFile.
 *
 * Live-only: reads the source archive name via broker mods.meta_read, verifies
 * the archive still exists in MO2 downloads, then delegates to MO2's installMod
 * primitive with the installed mod's name as the suggestion.
 */
import { z } from "zod";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { readMoIni } from "../mo-ini.js";
import { resolveProfileDir } from "../path-helpers.js";
const FomodChoiceSchema = z.object({
    page_name: z.string(),
    selected_options: z.array(z.object({ group_name: z.string(), option_name: z.string() })),
});
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        name: z.string(),
        fomod_choices: z.array(FomodChoiceSchema).optional(),
    }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);
function _extractInstallationFile(resp) {
    if (!resp.ok)
        throw new Error(resp.error?.message ?? "mods.meta_read failed");
    const installFile = resp.result?.meta?.General?.installationFile;
    if (!installFile) {
        throw new Error("no_installation_file_in_meta_ini: cannot reinstall this mod (likely added pre-MO2-2.x)");
    }
    return installFile;
}
async function _readInstallSource(args, ctx) {
    if (!ctx.pipeClient)
        throw new Error("live_mo2_required_for_reinstall");
    const name = args.name;
    const meta = await ctx.pipeClient.call("mods.meta_read", { name });
    const installFile = _extractInstallationFile(meta);
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const downloadsDir = ini.settings.downloadDirectory ?? join(ctx.config.mo2Root, "downloads");
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    const archivePath = join(downloadsDir, installFile);
    if (!existsSync(archivePath))
        throw new Error(`archive_not_in_downloads: ${installFile}`);
    return { installFile, archivePath, modPath: join(modsDir, name) };
}
async function _detectFomod(ctx, archivePath) {
    if (!ctx.sidecar)
        return false;
    try {
        await ctx.sidecar.call("fomod.parse_choices", { archive_path: archivePath });
        return true;
    }
    catch (e) {
        if (e instanceof Error && /not_a_fomod|info\.xml/i.test(e.message))
            return false;
        throw e;
    }
}
const handler = {
    toolName: "mo2_reinstall_mod",
    async buildPlan(args, ctx) {
        const name = args.name;
        const { installFile: _installFile, archivePath, modPath } = await _readInstallSource(args, ctx);
        return {
            diff: `Reinstall ${name} from ${archivePath}. Priority + meta preserved; content replaced.`,
            affectedFiles: [modPath],
            targets: [{ path: modPath, kind: "directory" }],
        };
    },
    async applyMutation(plan, ctx) {
        if (!ctx.pipeClient)
            throw new Error("live_mo2_required_for_reinstall");
        const name = plan.args.name;
        const { installFile, archivePath } = await _readInstallSource(plan.args, ctx);
        const isFomod = await _detectFomod(ctx, archivePath);
        if (isFomod && !plan.args.fomod_choices) {
            throw new Error("fomod_choices_required_for_reinstall");
        }
        const resp = await ctx.pipeClient.call("installation.install_local_archive", {
            archive_path: archivePath,
            name_suggestion: name,
        });
        if (!resp.ok)
            throw new Error(resp.error?.message ?? "installation.install_local_archive failed");
        if (ctx.sidecar) {
            await ctx.sidecar.call("world.invalidate", {
                profile_dir: resolveProfileDir(ctx, "Default"),
            });
        }
        return { reinstalled: name, archive: installFile, fomod_used: isFomod };
    },
};
registerTool({
    name: "mo2_reinstall_mod",
    tier: "T3",
    description: "Reinstall mod from its meta.ini[installationFile]. Requires file in downloads/. FOMOD requires fomod_choices.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
