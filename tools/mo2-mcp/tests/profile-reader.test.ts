import { describe, it, expect } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { readProfile } from "../src/profile-reader.js";

async function fixture(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "profile-"));
  const profileDir = join(root, "Default");
  await mkdir(profileDir, { recursive: true });
  return profileDir;
}

describe("readProfile", () => {
  it("reads modlist.txt with priority inversion (top = highest)", async () => {
    const dir = await fixture();
    await writeFile(
      join(dir, "modlist.txt"),
      "+TopMod\n+MiddleMod\n-BottomMod\n",
      "utf8",
    );
    await writeFile(join(dir, "plugins.txt"), "", "utf8");

    const profile = await readProfile(dir);

    expect(profile.mods).toHaveLength(3);
    expect(profile.mods[0].name).toBe("TopMod");
    expect(profile.mods[0].priority).toBe(2);
    expect(profile.mods[0].enabled).toBe(true);

    expect(profile.mods[1].name).toBe("MiddleMod");
    expect(profile.mods[1].priority).toBe(1);

    expect(profile.mods[2].name).toBe("BottomMod");
    expect(profile.mods[2].priority).toBe(0);
    expect(profile.mods[2].enabled).toBe(false);
  });

  it("detects separators by _separator suffix", async () => {
    const dir = await fixture();
    await writeFile(
      join(dir, "modlist.txt"),
      "+ModA\n+MySection_separator\n+ModB\n",
      "utf8",
    );
    await writeFile(join(dir, "plugins.txt"), "", "utf8");

    const profile = await readProfile(dir);

    expect(profile.mods[1].isSeparator).toBe(true);
    expect(profile.mods[0].isSeparator).toBe(false);
    expect(profile.mods[2].isSeparator).toBe(false);
  });

  it("reads plugins.txt with correct * polarity (* = enabled)", async () => {
    const dir = await fixture();
    await writeFile(join(dir, "modlist.txt"), "", "utf8");
    await writeFile(
      join(dir, "plugins.txt"),
      "*Fallout4.esm\n*DLCRobot.esm\nDisabledMod.esp\n# this is a comment\n",
      "utf8",
    );

    const profile = await readProfile(dir);

    expect(profile.plugins).toHaveLength(4);
    expect(profile.plugins[0]).toMatchObject({
      name: "Fallout4.esm",
      enabled: true,
      isComment: false,
    });
    expect(profile.plugins[1]).toMatchObject({ name: "DLCRobot.esm", enabled: true });
    expect(profile.plugins[2]).toMatchObject({ name: "DisabledMod.esp", enabled: false });
    expect(profile.plugins[3]).toMatchObject({
      name: "this is a comment",
      enabled: false,
      isComment: true,
    });
  });

  it("handles missing plugins.txt gracefully", async () => {
    const dir = await fixture();
    await writeFile(join(dir, "modlist.txt"), "+ModA\n", "utf8");

    const profile = await readProfile(dir);

    expect(profile.mods).toHaveLength(1);
    expect(profile.plugins).toEqual([]);
    expect(profile.pluginsMtimeMs).toBe(0);
  });

  it("returns mtime for cache invalidation", async () => {
    const dir = await fixture();
    await writeFile(join(dir, "modlist.txt"), "+ModA\n", "utf8");
    await writeFile(join(dir, "plugins.txt"), "*Foo.esp\n", "utf8");

    const profile = await readProfile(dir);

    expect(profile.modlistMtimeMs).toBeGreaterThan(0);
    expect(profile.pluginsMtimeMs).toBeGreaterThan(0);
  });

  it("filters comments and blank lines from modlist", async () => {
    const dir = await fixture();
    await writeFile(
      join(dir, "modlist.txt"),
      "+TopMod\n\n# comment line\n+BottomMod\n",
      "utf8",
    );
    await writeFile(join(dir, "plugins.txt"), "", "utf8");

    const profile = await readProfile(dir);

    expect(profile.mods).toHaveLength(2);
    expect(profile.mods.map((m) => m.name)).toEqual(["TopMod", "BottomMod"]);
  });

  it("infers profile name from directory", async () => {
    const dir = await fixture();
    await writeFile(join(dir, "modlist.txt"), "", "utf8");
    await writeFile(join(dir, "plugins.txt"), "", "utf8");

    const profile = await readProfile(dir);

    expect(profile.name).toBe("Default");
  });
});
