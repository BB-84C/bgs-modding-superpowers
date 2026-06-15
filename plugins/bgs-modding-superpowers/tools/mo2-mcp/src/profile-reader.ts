/**
 * MO2 profile reader — native TS, no subprocess on the hot path.
 *
 * Reads:
 * - <profile>/modlist.txt: lines prefixed `+` (enabled) / `-` (disabled).
 *   Top of file = highest priority (oracle §1.2). We INVERT line index so
 *   priority field matches mobase IModList semantics (priority 0 = lowest = bottom).
 * - <profile>/plugins.txt: lines prefixed `*` = enabled (FO4/SSE convention).
 *   Comments start with `#`. NOT charrdge's inverted polarity (librarian §1.3.9).
 *
 * Returns mtime for both files so callers can build mtime-keyed caches.
 */
import { readFile, stat } from "node:fs/promises";
import { join } from "node:path";

export interface ProfileMod {
  name: string;
  priority: number;
  enabled: boolean;
  isSeparator: boolean;
}

export interface ProfilePlugin {
  name: string;
  enabled: boolean;
  isComment: boolean;
}

export interface Profile {
  path: string;
  name: string;
  mods: ProfileMod[];
  plugins: ProfilePlugin[];
  modlistMtimeMs: number;
  pluginsMtimeMs: number;
}

export async function readProfile(profileDir: string): Promise<Profile> {
  const modlistPath = join(profileDir, "modlist.txt");
  const pluginsPath = join(profileDir, "plugins.txt");

  const [modlistText, pluginsText] = await Promise.all([
    readFile(modlistPath, "utf8"),
    readFile(pluginsPath, "utf8").catch(() => ""),
  ]);

  const modlistStat = await stat(modlistPath);
  let pluginsMtimeMs = 0;
  try {
    pluginsMtimeMs = (await stat(pluginsPath)).mtimeMs;
  } catch {
    // plugins.txt may be absent in rare profile states.
  }

  const rawLines = modlistText
    .split(/\r?\n/)
    .filter((line) => line.length > 0 && !line.startsWith("#"));
  const modCount = rawLines.length;

  const mods: ProfileMod[] = rawLines.map((line, idx) => {
    const enabled = line.startsWith("+");
    const isSeparator = line.endsWith("_separator");
    const name = line.replace(/^[+\-*]/, "");
    return {
      name,
      enabled,
      isSeparator,
      priority: modCount - 1 - idx,
    };
  });

  const plugins: ProfilePlugin[] = pluginsText
    .split(/\r?\n/)
    .filter((line) => line.length > 0)
    .map((line) => {
      const isComment = line.startsWith("#");
      const enabled = !isComment && line.startsWith("*");
      const name = line.replace(/^[#*]/, "").trim();
      return { name, enabled, isComment };
    });

  return {
    path: profileDir,
    name: profileDir.split(/[/\\]/).pop() ?? "",
    mods,
    plugins,
    modlistMtimeMs: modlistStat.mtimeMs,
    pluginsMtimeMs,
  };
}
