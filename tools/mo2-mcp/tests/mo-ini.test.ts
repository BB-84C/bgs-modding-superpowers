import { describe, it, expect } from "vitest";
import { mkdtemp, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { readMoIni, decodeIniValue, resolveGameKey, resolveGameName } from "../src/mo-ini.js";

describe("readMoIni", () => {
  it("parses General + Settings + customExecutables", async () => {
    const dir = await mkdtemp(join(tmpdir(), "mo-ini-"));
    const iniPath = join(dir, "ModOrganizer.ini");
    await writeFile(
      iniPath,
      `[General]
game=fallout4
gameName=Fallout 4
gamePath=C:/Games/Fallout4

[Settings]
base_directory=C:/MO2/Fallout4
mod_directory=C:/MO2/Fallout4/mods
download_directory=C:/MO2/Fallout4/downloads

[customExecutables]
size=2
1\\title=xEdit
1\\binary=C:/Tools/xEdit/xEdit.exe
1\\arguments=-fo4
1\\workingDirectory=C:/Tools/xEdit
1\\steamAppID=
1\\ownicon=true
1\\hide=false
2\\title=LOOT
2\\binary=C:/LOOT/LOOT.exe
2\\arguments=
2\\workingDirectory=
2\\steamAppID=
2\\ownicon=false
2\\hide=false
`,
      "utf8",
    );

    const ini = await readMoIni(iniPath);

    expect(ini.general.game).toBe("fallout4");
    expect(ini.general.gameName).toBe("Fallout 4");
    expect(ini.settings.modDirectory).toBe("C:/MO2/Fallout4/mods");
    expect(ini.customExecutables).toHaveLength(2);
    expect(ini.customExecutables[0]).toMatchObject({
      title: "xEdit",
      binary: "C:/Tools/xEdit/xEdit.exe",
      arguments: "-fo4",
      ownicon: true,
      hide: false,
    });
    expect(ini.customExecutables[1].title).toBe("LOOT");
  });

  it("preserves section ranges for verbatim rewrite", async () => {
    const dir = await mkdtemp(join(tmpdir(), "mo-ini-"));
    const iniPath = join(dir, "ModOrganizer.ini");
    await writeFile(
      iniPath,
      `[General]
game=skyrimSE

[customExecutables]
size=1
1\\title=SKSE
1\\binary=C:/skse.exe

[OtherSection]
unrelated=value
`,
      "utf8",
    );

    const ini = await readMoIni(iniPath);

    expect(ini.sectionRanges.has("General")).toBe(true);
    expect(ini.sectionRanges.has("customExecutables")).toBe(true);
    expect(ini.sectionRanges.has("OtherSection")).toBe(true);

    const customRange = ini.sectionRanges.get("customExecutables")!;
    expect(customRange[1]).toBeGreaterThan(customRange[0]);
  });

  it("handles empty customExecutables section", async () => {
    const dir = await mkdtemp(join(tmpdir(), "mo-ini-"));
    const iniPath = join(dir, "ModOrganizer.ini");
    await writeFile(
      iniPath,
      `[General]
game=fallout4

[customExecutables]
size=0
`,
      "utf8",
    );

    const ini = await readMoIni(iniPath);
    expect(ini.customExecutables).toEqual([]);
  });

  it("handles missing customExecutables section", async () => {
    const dir = await mkdtemp(join(tmpdir(), "mo-ini-"));
    const iniPath = join(dir, "ModOrganizer.ini");
    await writeFile(
      iniPath,
      `[General]
game=fallout4
`,
      "utf8",
    );

    const ini = await readMoIni(iniPath);
    expect(ini.customExecutables).toEqual([]);
  });

  it("reads General.selected_profile from underscore key", async () => {
    const dir = await mkdtemp(join(tmpdir(), "mo-ini-"));
    const iniPath = join(dir, "ModOrganizer.ini");
    await writeFile(
      iniPath,
      `[General]
game=fallout4
selected_profile=Modding
`,
      "utf8",
    );

    const ini = await readMoIni(iniPath);
    expect(ini.general.selectedProfile).toBe("Modding");
  });

  it("decodes @ByteArray-wrapped selected_profile with \\xHH byte escapes (Chinese)", async () => {
    // Regression: real Starfield install observed 2026-06-24 stored
    // `selected_profile=@ByteArray(BB84\xe8\x87\xaa\xe7\x94\xa8\x32)` which
    // decodes to `BB84自用2` (UTF-8 bytes E8 87 AA = 自, E7 94 A8 = 用).
    const dir = await mkdtemp(join(tmpdir(), "mo-ini-"));
    const iniPath = join(dir, "ModOrganizer.ini");
    await writeFile(
      iniPath,
      `[General]
gameName=Starfield
selected_profile=@ByteArray(BB84\\xe8\\x87\\xaa\\xe7\\x94\\xa8\\x32)
gamePath=@ByteArray(D:\\\\SteamLibrary\\\\steamapps\\\\common\\\\Starfield)
`,
      "utf8",
    );

    const ini = await readMoIni(iniPath);
    expect(ini.general.selectedProfile).toBe("BB84自用2");
    expect(ini.general.gamePath).toBe("D:\\SteamLibrary\\steamapps\\common\\Starfield");
    expect(ini.general.gameName).toBe("Starfield");
  });
});

describe("decodeIniValue", () => {
  it("returns plain values unchanged", () => {
    expect(decodeIniValue("Starfield")).toBe("Starfield");
    expect(decodeIniValue("")).toBe("");
    expect(decodeIniValue("Fallout 4")).toBe("Fallout 4");
  });

  it("decodes @ByteArray with double-backslash escapes (Windows paths)", () => {
    expect(decodeIniValue("@ByteArray(D:\\\\Games\\\\Skyrim)")).toBe("D:\\Games\\Skyrim");
  });

  it("decodes @ByteArray with \\xHH byte escapes to UTF-8 string (Chinese)", () => {
    // BB84 + UTF-8 bytes for 自用 + "2"
    expect(decodeIniValue("@ByteArray(BB84\\xe8\\x87\\xaa\\xe7\\x94\\xa8\\x32)")).toBe(
      "BB84自用2",
    );
  });

  it("decodes mixed \\xHH + double-backslash + plain ASCII", () => {
    // "D:\Starfield 自用\\save" with both kinds of escapes
    expect(
      decodeIniValue("@ByteArray(D:\\\\Starfield \\xe8\\x87\\xaa\\xe7\\x94\\xa8\\\\save)"),
    ).toBe("D:\\Starfield 自用\\save");
  });

  it("treats unknown \\X escape as literal backslash + next char", () => {
    expect(decodeIniValue("@ByteArray(foo\\zbar)")).toBe("foo\\zbar");
  });
});

describe("resolveGameKey", () => {
  it("returns game field as-is when present (older MO2)", () => {
    expect(resolveGameKey({ game: "fallout4" })).toBe("fallout4");
    expect(resolveGameKey({ game: "skyrimSE" })).toBe("skyrimSE");
  });

  it("maps gameName TitleCase to lowercase key when game absent (modern MO2)", () => {
    expect(resolveGameKey({ gameName: "Starfield" })).toBe("starfield");
    expect(resolveGameKey({ gameName: "Fallout4" })).toBe("fallout4");
    expect(resolveGameKey({ gameName: "SkyrimSE" })).toBe("skyrimSE");
    expect(resolveGameKey({ gameName: "SkyrimAE" })).toBe("skyrimSE");
    expect(resolveGameKey({ gameName: "FalloutNV" })).toBe("falloutNV");
  });

  it("falls back to lowercased gameName for unmapped names", () => {
    expect(resolveGameKey({ gameName: "FutureGame" })).toBe("futuregame");
  });

  it("prefers game over gameName when both are present", () => {
    expect(resolveGameKey({ game: "fallout4", gameName: "Starfield" })).toBe("fallout4");
  });

  it("defaults to fallout4 when both are missing", () => {
    expect(resolveGameKey({})).toBe("fallout4");
  });
});

describe("resolveGameName", () => {
  it("returns gameName as-is when present (modern MO2)", () => {
    expect(resolveGameName({ gameName: "Starfield" })).toBe("Starfield");
    expect(resolveGameName({ gameName: "Fallout4" })).toBe("Fallout4");
  });

  it("reverse-maps from game key when only game is present (older MO2)", () => {
    expect(resolveGameName({ game: "starfield" })).toBe("Starfield");
    expect(resolveGameName({ game: "fallout4" })).toBe("Fallout4");
    expect(resolveGameName({ game: "skyrimSE" })).toBe("SkyrimSE");
  });

  it("prefers gameName over game when both are present", () => {
    expect(resolveGameName({ game: "fallout4", gameName: "Starfield" })).toBe("Starfield");
  });

  it("defaults to Fallout4 when both are missing", () => {
    expect(resolveGameName({})).toBe("Fallout4");
  });

  it("defaults to Fallout4 for unknown game key (no reverse mapping)", () => {
    expect(resolveGameName({ game: "futuregame" })).toBe("Fallout4");
  });
});
