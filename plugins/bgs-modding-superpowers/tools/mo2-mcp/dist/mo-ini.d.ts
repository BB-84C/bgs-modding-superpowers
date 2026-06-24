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
export declare function decodeIniValue(value: string): string;
/**
 * Resolve the lowercase internal game KEY (e.g. "starfield", "fallout4") from
 * a parsed `[General]` section. Prefers an explicit `game=` field; falls back
 * to mapping `gameName=` (the modern-MO2 field that newer installs use); final
 * fallback is "fallout4" (legacy default to preserve existing behavior).
 */
export declare function resolveGameKey(general: {
    game?: string;
    gameName?: string;
}): string;
/**
 * Resolve the TitleCase display NAME (e.g. "Starfield", "Fallout4") for
 * meta.ini `gameName=` field writes and for per-game INI filename prefixes
 * (e.g. `Starfield.ini`, `StarfieldPrefs.ini`). Prefers `gameName=` directly;
 * falls back to mapping `game=` (older MO2) via the reverse map; final
 * fallback is "Fallout4".
 */
export declare function resolveGameName(general: {
    game?: string;
    gameName?: string;
}): string;
export declare function readMoIni(path: string): Promise<MoIni>;
