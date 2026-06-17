/**
 * mo2_profile_ini_get — T1 read profile-local game INI.
 *
 * Reads <profile>/<game>.ini, <game>Prefs.ini, or <game>Custom.ini.
 * Falls back to %DOCUMENTS%/My Games/<Game>/ if profile-local INIs not enabled.
 */
import { z } from "zod";
import { readFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { readMoIni } from "../mo-ini.js";
import { requireBoundContext } from "../binding.js";
const inputSchema = z.object({
    profile: z.string().default("Default"),
    ini_name: z.enum(["game", "prefs", "custom"]),
    section: z.string().optional(),
    key: z.string().optional(),
});
const INI_SUFFIXES = ["", "Prefs", "Custom"];
const GAME_INI_BASES = [
    "Fallout4",
    "Fallout4VR",
    "SkyrimSE",
    "SkyrimAE",
    "SkyrimVR",
    "Skyrim",
    "Starfield",
    "FalloutNV",
    "Fallout3",
    "Oblivion",
];
const GAME_ALIASES = {
    fallout4: "Fallout4",
    fallout4vr: "Fallout4VR",
    skyrimse: "SkyrimSE",
    skyrimspecialedition: "SkyrimSE",
    skyrimae: "SkyrimAE",
    skyrimanniversaryedition: "SkyrimAE",
    skyrimvr: "SkyrimVR",
    skyrimle: "Skyrim",
    skyrimlegendaryedition: "Skyrim",
    skyrim: "Skyrim",
    starfield: "Starfield",
    falloutnv: "FalloutNV",
    falloutnewvegas: "FalloutNV",
    newvegas: "FalloutNV",
    fallout3: "Fallout3",
    oblivion: "Oblivion",
};
function parseIni(text) {
    const sections = {};
    let current = "";
    for (const line of text.split(/\r?\n/)) {
        const m = line.match(/^\[(.+)\]$/);
        if (m) {
            current = m[1];
            sections[current] = sections[current] ?? {};
            continue;
        }
        if (!current)
            continue;
        const eq = line.indexOf("=");
        if (eq > 0)
            sections[current][line.slice(0, eq).trim()] = line.slice(eq + 1);
    }
    return sections;
}
function normalizeGameKey(value) {
    return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}
function gameIniBaseFromIdentifier(value) {
    const trimmed = value?.trim();
    if (!trimmed)
        return null;
    const normalized = normalizeGameKey(trimmed);
    return GAME_ALIASES[normalized] ?? trimmed;
}
async function gameIniBaseFromProfileFiles(profileDir) {
    const entries = await readdir(profileDir).catch(() => []);
    const names = new Set(entries.map((entry) => entry.toLowerCase()));
    for (const base of GAME_INI_BASES) {
        for (const suffix of INI_SUFFIXES) {
            if (names.has(`${base}${suffix}.ini`.toLowerCase()))
                return base;
        }
    }
    return null;
}
function gameIniBaseFromGamePath(gamePath) {
    const trimmed = gamePath?.trim().replace(/[\\/]+$/g, "");
    if (!trimmed)
        return null;
    const leaf = trimmed.split(/[\\/]/).filter(Boolean).pop();
    return gameIniBaseFromIdentifier(leaf);
}
async function resolveGameIniBase(args) {
    return (gameIniBaseFromIdentifier(args.ini.general.game) ??
        (await gameIniBaseFromProfileFiles(join(args.mo2Root, "profiles", args.profile))) ??
        gameIniBaseFromGamePath(args.ini.general.gamePath));
}
registerTool({
    name: "mo2_profile_ini_get",
    tier: "T1",
    description: "Read profile-local game INI (<game>.ini, <game>Prefs.ini, or <game>Custom.ini). Returns sections, a specific section, or a specific key. Falls back to %DOCUMENTS% if profile-local INIs absent.",
    inputSchema,
    handler: async (args, ctx) => {
        const bound = requireBoundContext(ctx);
        const profile = args.profile ?? "Default";
        const iniName = args.ini_name;
        const ini = await readMoIni(join(bound.config.mo2Root, "ModOrganizer.ini"));
        const game = await resolveGameIniBase({ mo2Root: bound.config.mo2Root, profile, ini });
        if (!game) {
            return {
                ok: false,
                error: {
                    code: "no_game_set",
                    message: "ModOrganizer.ini [General] game= missing and no fallback game could be derived",
                },
            };
        }
        const fileMap = {
            game: `${game}.ini`,
            prefs: `${game}Prefs.ini`,
            custom: `${game}Custom.ini`,
        };
        const fileName = fileMap[iniName];
        const localPath = join(bound.config.mo2Root, "profiles", profile, fileName);
        let text;
        let source;
        try {
            text = await readFile(localPath, "utf8");
            source = "profile_local";
        }
        catch {
            const userProfile = process.env.USERPROFILE;
            if (userProfile) {
                const docsPath = join(userProfile, "Documents", "My Games", game, fileName);
                try {
                    text = await readFile(docsPath, "utf8");
                    source = "documents";
                }
                catch {
                    return { ok: false, error: { code: "ini_not_found", message: fileName } };
                }
            }
            else {
                return { ok: false, error: { code: "ini_not_found", message: fileName } };
            }
        }
        const sections = parseIni(text);
        if (args.section && args.key) {
            return {
                ok: true,
                result: {
                    source,
                    ini_name: iniName,
                    value: sections[args.section]?.[args.key],
                },
                error: null,
            };
        }
        if (args.section) {
            return {
                ok: true,
                result: {
                    source,
                    ini_name: iniName,
                    section: sections[args.section] ?? {},
                },
                error: null,
            };
        }
        return { ok: true, result: { source, ini_name: iniName, sections }, error: null };
    },
});
