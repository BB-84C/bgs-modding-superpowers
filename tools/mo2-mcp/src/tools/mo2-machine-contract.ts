/**
 * mo2_machine_contract — T1 paths-only snapshot.
 *
 * Per charrdge pattern (oracle Unique catches): return absolute paths the
 * agent can natively Read itself, instead of payloads. Cheap; agent uses
 * Read tool on returned paths for hot-path follow-ups.
 */
import { z } from "zod";
import { join } from "node:path";
import { existsSync } from "node:fs";
import { readdir } from "node:fs/promises";
import { registerTool } from "../tool-registry.js";
import { readMoIni } from "../mo-ini.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";

const inputSchema = z.object({
  only_enabled: z.boolean().default(false),
});

registerTool({
  name: "mo2_machine_contract",
  tier: "T1",
  description:
    "Paths-only snapshot (charrdge pattern): returns absolute paths the agent can read natively without further MCP calls. Saves token budget on large modpacks.",
  inputSchema,
  handler: async (_args, ctx) => {
    if (bindingSnapshot(ctx).state !== "bound") {
      return {
        ok: true,
        result: { bound: false, hint: "call mo2_session({ mo2Root }) to bind" },
        error: null,
      };
    }
    const bound = requireBoundContext(ctx);
    const ini = await readMoIni(join(bound.config.mo2Root, "ModOrganizer.ini"));
    const profileName = bound.config.allowedProfiles[0];
    const profileDir = join(bound.config.mo2Root, "profiles", profileName);
    const modsDir = ini.settings.modDirectory ?? join(bound.config.mo2Root, "mods");
    const gamePath = ini.general.gamePath ?? null;
    const xeditCandidate = gamePath ? join(gamePath, "Tools", "OpenCodeXEdit", "xEdit.exe") : null;

    const allMods = await readdir(modsDir, { withFileTypes: true }).catch(() => []);
    const archiveSearchRoots = allMods
      .filter((d) => d.isDirectory())
      .map((d) => ({
        mod_name: d.name,
        mod_root_abs: join(modsDir, d.name),
        effective_data_root_abs: existsSync(join(modsDir, d.name, "Data"))
          ? join(modsDir, d.name, "Data")
          : join(modsDir, d.name),
        is_data_subdir_layout: existsSync(join(modsDir, d.name, "Data")),
      }));

    return {
      ok: true,
      result: {
        mod_organizer_exe: join(bound.config.mo2Root, "ModOrganizer.exe"),
        game_path: gamePath,
        stock_game_path: gamePath?.toLowerCase().includes("stock game") ? gamePath : null,
        xedit_target: xeditCandidate && existsSync(xeditCandidate) ? xeditCandidate : null,
        profile_list_paths: {
          modlist_txt: join(profileDir, "modlist.txt"),
          plugins_txt: join(profileDir, "plugins.txt"),
          loadorder_txt: join(profileDir, "loadorder.txt"),
          profile_dir: profileDir,
        },
        profile_inis: {
          game_ini: existsSync(join(profileDir, `${ini.general.game}.ini`))
            ? join(profileDir, `${ini.general.game}.ini`)
            : null,
          gameprefs_ini: existsSync(join(profileDir, `${ini.general.game}Prefs.ini`))
            ? join(profileDir, `${ini.general.game}Prefs.ini`)
            : null,
        },
        mod_organizer_ini: join(bound.config.mo2Root, "ModOrganizer.ini"),
        archive_search_roots: archiveSearchRoots,
      },
      error: null,
    };
  },
});
