import { describe, it, expect } from "vitest";
import { mkdtemp, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { readMoIni } from "../src/mo-ini.js";

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
});
