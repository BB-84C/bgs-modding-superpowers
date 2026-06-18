/**
 * mo2-state-for-fomod — gather the MO2 state shape that the sidecar's FOMOD
 * dependency evaluator expects (Lane V3 FOMOD-EXT phase 4).
 *
 * The sidecar's `fomod.parse_choices` / `fomod.resolve_files` / `install.stage_fomod`
 * accept an optional `mo2_state` parameter:
 *   {
 *     enabled_plugins: string[],   // plugin filenames enabled in plugins.txt
 *     game_version:    string | null,
 *     provided_files:  string[],   // optional, used for non-plugin <fileDependency>
 *   }
 *
 * This module reads the profile's plugins.txt + modlist.txt and ModOrganizer.ini
 * once per call and produces that shape. `provided_files` is intentionally left
 * empty in v1.3 — walking every enabled mod's tree on every FOMOD parse is too
 * expensive for the typical case where <fileDependency> targets a plugin (.esp/.esm/.esl),
 * and pyfomod's `file_type` callback returns MISSING for unknown non-plugin
 * paths, which matches the "we don't know yet" reality. A future enhancement
 * (v1.4+) can lazily populate provided_files by scanning enabled mods only when
 * the FOMOD declares non-plugin file dependencies.
 *
 * Game version detection: ModOrganizer.ini does NOT carry a game-version field
 * by default (MO2 obtains it from the executable at launch time). We surface
 * the value via the optional `[General] gameVersion=` if present and fall back
 * to null otherwise. pyfomod's `<gameDependency>` check is silently skipped
 * when game_version is null (mirrors pyfomod's `_test_version_condition`).
 */
import { join } from "node:path";
import { readProfile } from "./profile-reader.js";
import { readMoIni } from "./mo-ini.js";
import type { ToolContext } from "./types.js";
import { requireBoundContext } from "./binding.js";

export interface Mo2FomodState {
  enabled_plugins: string[];
  game_version: string | null;
  provided_files: string[];
}

/**
 * Read enabled plugins from `<profile>/plugins.txt`, game version (best-effort)
 * from `ModOrganizer.ini`, and return the shape the sidecar expects.
 *
 * Failures (missing profile dir, malformed INI) downgrade to an empty state
 * rather than throwing — the sidecar treats an empty state as "no dependency
 * info" and parse_choices still works, just without dependencies_status fields.
 */
export async function gatherMo2FomodState(
  ctx: ToolContext,
  profile: string,
): Promise<Mo2FomodState> {
  const bound = requireBoundContext(ctx);
  const profileDir = join(bound.config.mo2Root, "profiles", profile);

  let enabledPlugins: string[] = [];
  try {
    const prof = await readProfile(profileDir);
    enabledPlugins = prof.plugins
      .filter((p) => p.enabled && !p.isComment)
      .map((p) => p.name)
      .filter((n) => n.length > 0);
  } catch {
    // Profile may be absent in fresh installs; that's fine — caller can still
    // proceed without dependency evaluation.
  }

  let gameVersion: string | null = null;
  try {
    const ini = await readMoIni(join(bound.config.mo2Root, "ModOrganizer.ini"));
    // MO2's [General] section may carry `gameVersion=` on some setups but it
    // is not guaranteed. Surface whatever is there; otherwise leave null.
    const generalAny = ini.general as Record<string, unknown>;
    const gv = generalAny["gameVersion"];
    if (typeof gv === "string" && gv.length > 0) {
      gameVersion = gv;
    }
  } catch {
    // INI missing or malformed — leave null.
  }

  return {
    enabled_plugins: enabledPlugins,
    game_version: gameVersion,
    provided_files: [],
  };
}
