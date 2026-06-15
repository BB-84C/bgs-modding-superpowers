/**
 * ModOrganizer.ini parser.
 *
 * Handles Qt QSettings INI array dialect for [customExecutables]:
 *   size=2
 *   1\title=xEdit
 *   1\binary=...
 *   2\title=LOOT
 *
 * Preserves other sections verbatim via sectionRanges so future writes
 * (e.g., mo2_configure_executable in S4) can replace [customExecutables]
 * without touching anything else.
 */
import { readFile } from "node:fs/promises";

export interface MoIniCustomExecutable {
  title: string;
  binary: string;
  arguments?: string;
  workingDirectory?: string;
  steamAppID?: string;
  ownicon?: boolean;
  hide?: boolean;
  toolbar?: boolean;
  minimizeToSystemTray?: boolean;
}

export interface MoIni {
  raw: string;
  general: {
    game?: string;
    gameName?: string;
    gamePath?: string;
    selectedProfile?: string;
  };
  settings: {
    baseDirectory?: string;
    modDirectory?: string;
    downloadDirectory?: string;
    profilesDirectory?: string;
    overwriteDirectory?: string;
    cacheDirectory?: string;
  };
  customExecutables: MoIniCustomExecutable[];
  /** Section name -> [startLine, endLine] inclusive, zero-based line numbers in `raw`. */
  sectionRanges: Map<string, [number, number]>;
}

const BOOL_KEYS = new Set(["ownicon", "hide", "toolbar", "minimizeToSystemTray"]);

export async function readMoIni(path: string): Promise<MoIni> {
  const raw = await readFile(path, "utf8");
  const lines = raw.split(/\r?\n/);

  const sectionRanges = new Map<string, [number, number]>();
  const sectionLines = new Map<string, string[]>();
  let currentSection = "";
  let sectionStart = 0;

  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].trim().match(/^\[(.+)\]$/);
    if (match) {
      if (currentSection) sectionRanges.set(currentSection, [sectionStart, i - 1]);
      currentSection = match[1];
      sectionStart = i;
      sectionLines.set(currentSection, []);
    } else if (currentSection) {
      sectionLines.get(currentSection)!.push(lines[i]);
    }
  }
  if (currentSection) sectionRanges.set(currentSection, [sectionStart, lines.length - 1]);

  const parseFlat = (sectionName: string): Record<string, string> => {
    const result: Record<string, string> = {};
    for (const line of sectionLines.get(sectionName) ?? []) {
      const eq = line.indexOf("=");
      if (eq > 0) result[line.slice(0, eq).trim()] = line.slice(eq + 1);
    }
    return result;
  };

  const general = parseFlat("General");
  const settings = parseFlat("Settings");

  const customExecutables: MoIniCustomExecutable[] = [];
  const customFlat = parseFlat("customExecutables");
  const size = Number.parseInt(customFlat.size ?? "0", 10);
  const entryCount = Number.isFinite(size) ? size : 0;

  for (let i = 1; i <= entryCount; i++) {
    const entry: Record<string, string | boolean> = {};
    for (const [key, value] of Object.entries(customFlat)) {
      const parts = key.split("\\");
      if (parts.length !== 2 || parts[0] !== String(i)) continue;

      const subKey = parts[1];
      if (BOOL_KEYS.has(subKey)) {
        entry[subKey] = value.trim().toLowerCase() === "true";
      } else {
        entry[subKey] = value;
      }
    }

    if (typeof entry.title === "string") {
      customExecutables.push(entry as unknown as MoIniCustomExecutable);
    }
  }

  return {
    raw,
    general: {
      game: general.game,
      gameName: general.gameName,
      gamePath: general.gamePath,
      selectedProfile: general.selected_profile,
    },
    settings: {
      baseDirectory: settings.base_directory,
      modDirectory: settings.mod_directory,
      downloadDirectory: settings.download_directory,
      profilesDirectory: settings.profiles_directory,
      overwriteDirectory: settings.overwrite_directory,
      cacheDirectory: settings.cache_directory,
    },
    customExecutables,
    sectionRanges,
  };
}
