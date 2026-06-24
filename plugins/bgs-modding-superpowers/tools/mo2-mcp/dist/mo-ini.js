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
const BOOL_KEYS = new Set(["ownicon", "hide", "toolbar", "minimizeToSystemTray"]);
/**
 * Decode Qt QSettings `@ByteArray(...)` payload.
 *
 * Qt uses backslash-escape sequences to round-trip arbitrary bytes through a
 * 7-bit-safe INI value. The previous implementation only handled `\\` → `\`,
 * which broke Chinese / non-ASCII profile names (e.g. `selected_profile=
 * @ByteArray(BB84\xe8\x87\xaa\xe7\x94\xa8\x32)` decoded to literal
 * `BB84\xe8\x87...` and made every fs operation that joined the profile
 * dir fail with ENOENT). This implementation decodes:
 *   - `\xHH` (2 hex digits) → byte 0xHH
 *   - `\\`                   → byte 0x5C (backslash)
 *   - other `\<c>` sequences → literal backslash + literal `<c>`
 *   - ASCII chars            → their code byte
 *   - non-ASCII chars        → their UTF-8 bytes
 * The collected bytes are then decoded as UTF-8.
 */
export function decodeIniValue(value) {
    const byteArray = value.match(/^@ByteArray\((.*)\)$/);
    if (!byteArray)
        return value;
    const escaped = byteArray[1];
    const bytes = [];
    let i = 0;
    while (i < escaped.length) {
        const ch = escaped[i];
        if (ch === "\\") {
            if (i + 3 < escaped.length && escaped[i + 1] === "x") {
                const hex = escaped.substring(i + 2, i + 4);
                if (/^[0-9a-fA-F]{2}$/.test(hex)) {
                    bytes.push(parseInt(hex, 16));
                    i += 4;
                    continue;
                }
            }
            if (i + 1 < escaped.length && escaped[i + 1] === "\\") {
                bytes.push(0x5c);
                i += 2;
                continue;
            }
            // Unknown escape — preserve backslash and let next iteration handle the
            // following character.
            bytes.push(0x5c);
            i += 1;
            continue;
        }
        const code = ch.charCodeAt(0);
        if (code < 0x80) {
            bytes.push(code);
        }
        else {
            const enc = new TextEncoder().encode(ch);
            for (let j = 0; j < enc.length; j++)
                bytes.push(enc[j]);
        }
        i += 1;
    }
    return new TextDecoder("utf-8").decode(new Uint8Array(bytes));
}
/**
 * Map from MO2's `[General] gameName=` display string (TitleCase, e.g.
 * "Starfield", "Fallout4", "SkyrimSE") to the internal lowercase key used by
 * sidecar / MCP enums (e.g. "starfield", "fallout4", "skyrimSE"). The reverse
 * map is derived from this.
 *
 * If `gameName` is unknown, fall back to `gameName.toLowerCase()` — covers
 * future games without code changes, at the cost of possibly miss-routing on
 * a sidecar enum mismatch (caller is responsible for validating).
 */
const GAME_NAME_TO_KEY = {
    Starfield: "starfield",
    Fallout4: "fallout4",
    Fallout4VR: "fallout4",
    SkyrimSE: "skyrimSE",
    SkyrimAE: "skyrimSE",
    SkyrimVR: "skyrimSE",
    Skyrim: "skyrimLE",
    Oblivion: "oblivion",
    FalloutNV: "falloutNV",
    Fallout3: "fallout3",
    Morrowind: "morrowind",
    Enderal: "enderal",
    EnderalSE: "enderalSE",
};
const GAME_KEY_TO_NAME = (() => {
    const m = {};
    for (const [name, key] of Object.entries(GAME_NAME_TO_KEY)) {
        if (!(key in m))
            m[key] = name; // first-wins for shared keys (Fallout4VR→fallout4 etc.)
    }
    return m;
})();
/**
 * Resolve the lowercase internal game KEY (e.g. "starfield", "fallout4") from
 * a parsed `[General]` section. Prefers an explicit `game=` field; falls back
 * to mapping `gameName=` (the modern-MO2 field that newer installs use); final
 * fallback is "fallout4" (legacy default to preserve existing behavior).
 */
export function resolveGameKey(general) {
    if (general.game)
        return general.game;
    if (general.gameName) {
        return GAME_NAME_TO_KEY[general.gameName] ?? general.gameName.toLowerCase();
    }
    return "fallout4";
}
/**
 * Resolve the TitleCase display NAME (e.g. "Starfield", "Fallout4") for
 * meta.ini `gameName=` field writes and for per-game INI filename prefixes
 * (e.g. `Starfield.ini`, `StarfieldPrefs.ini`). Prefers `gameName=` directly;
 * falls back to mapping `game=` (older MO2) via the reverse map; final
 * fallback is "Fallout4".
 */
export function resolveGameName(general) {
    if (general.gameName)
        return general.gameName;
    if (general.game && GAME_KEY_TO_NAME[general.game])
        return GAME_KEY_TO_NAME[general.game];
    return "Fallout4";
}
export async function readMoIni(path) {
    const raw = await readFile(path, "utf8");
    const lines = raw.split(/\r?\n/);
    const sectionRanges = new Map();
    const sectionLines = new Map();
    let currentSection = "";
    let sectionStart = 0;
    for (let i = 0; i < lines.length; i++) {
        const match = lines[i].trim().match(/^\[(.+)\]$/);
        if (match) {
            if (currentSection)
                sectionRanges.set(currentSection, [sectionStart, i - 1]);
            currentSection = match[1];
            sectionStart = i;
            sectionLines.set(currentSection, []);
        }
        else if (currentSection) {
            sectionLines.get(currentSection).push(lines[i]);
        }
    }
    if (currentSection)
        sectionRanges.set(currentSection, [sectionStart, lines.length - 1]);
    const parseFlat = (sectionName) => {
        const result = {};
        for (const line of sectionLines.get(sectionName) ?? []) {
            const eq = line.indexOf("=");
            if (eq > 0)
                result[line.slice(0, eq).trim()] = decodeIniValue(line.slice(eq + 1));
        }
        return result;
    };
    const general = parseFlat("General");
    const settings = parseFlat("Settings");
    const customExecutables = [];
    const customFlat = parseFlat("customExecutables");
    const size = Number.parseInt(customFlat.size ?? "0", 10);
    const entryCount = Number.isFinite(size) ? size : 0;
    for (let i = 1; i <= entryCount; i++) {
        const entry = {};
        for (const [key, value] of Object.entries(customFlat)) {
            const parts = key.split("\\");
            if (parts.length !== 2 || parts[0] !== String(i))
                continue;
            const subKey = parts[1];
            if (BOOL_KEYS.has(subKey)) {
                entry[subKey] = value.trim().toLowerCase() === "true";
            }
            else {
                entry[subKey] = value;
            }
        }
        if (typeof entry.title === "string") {
            customExecutables.push(entry);
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
