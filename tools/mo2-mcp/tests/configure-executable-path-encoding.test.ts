/**
 * BUG-11 Layer B regression — forward-slash conversion for binary /
 * workingDirectory values written to ModOrganizer.ini.
 *
 * Backstory: writing `C:\\Windows\\System32\\notepad.exe` raw produced
 * `8\binary=C:\Windows\System32\notepad.exe` in the INI; Qt QSettings then
 * stripped the `\W` and `\S` escapes on read, corrupting the path to
 * `C:indowsystem32\notepad.exe`. MO2 raised a modal `Cannot launch program`
 * dialog, which blocked the Qt main thread and cascaded into broker hangs
 * (BUG-16).
 *
 * Real MO2 INIs (verified at orchestrator inspection time, e.g.
 * `.artifacts/mo2/ModOrganizer.ini`) store these values with forward
 * slashes and no @ByteArray wrapper:
 *   1\binary=D:/awesome-bgs-mod-master/.artifacts/mo2/Stock Game/Fallout 4/f4se_loader.exe
 * This test pins the serializer to that convention.
 */
import { describe, it, expect } from "vitest";
import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import {
  _serializeValue,
  _rewriteCustomExecutables,
} from "../src/tools/mo2-configure-executable.js";
import { readMoIni, type MoIniCustomExecutable } from "../src/mo-ini.js";

describe("_serializeValue path-key forward-slash normalization", () => {
  it("normalizes backslashes in binary to forward slashes", () => {
    expect(_serializeValue("binary", "C:\\Windows\\System32\\notepad.exe")).toBe(
      "C:/Windows/System32/notepad.exe",
    );
  });

  it("normalizes backslashes in workingDirectory to forward slashes", () => {
    expect(_serializeValue("workingDirectory", "C:\\Windows\\System32")).toBe(
      "C:/Windows/System32",
    );
  });

  it("does NOT normalize backslashes in title (arbitrary label, not a path)", () => {
    expect(_serializeValue("title", "My App With \\ Backslash")).toBe(
      "My App With \\ Backslash",
    );
  });

  it("does NOT normalize backslashes in arguments (verbatim CLI round-trip)", () => {
    const cli = '-D "D:\\Games\\Fallout 4"';
    expect(_serializeValue("arguments", cli)).toBe(cli);
  });

  it("serializes boolean true/false for any key (path-key true is still 'true')", () => {
    expect(_serializeValue("binary", true)).toBe("true");
    expect(_serializeValue("binary", false)).toBe("false");
    expect(_serializeValue("ownicon", true)).toBe("true");
    expect(_serializeValue("hide", false)).toBe("false");
  });

  it("leaves forward-slash binary input unchanged (round-trip stable)", () => {
    expect(_serializeValue("binary", "D:/already/forward/slash.exe")).toBe(
      "D:/already/forward/slash.exe",
    );
  });

  it("leaves empty path values unchanged", () => {
    expect(_serializeValue("binary", "")).toBe("");
    expect(_serializeValue("workingDirectory", "")).toBe("");
  });

  it("leaves backslash-free path values unchanged", () => {
    expect(_serializeValue("binary", "notepad.exe")).toBe("notepad.exe");
  });
});

describe("_rewriteCustomExecutables + readMoIni round-trip", () => {
  it("backslash binary written → readMoIni reads back forward-slash form (parses safely)", async () => {
    const dir = await mkdtemp(join(tmpdir(), "mo-cfg-exec-"));
    const iniPath = join(dir, "ModOrganizer.ini");
    try {
      const initial = "[General]\ngame=fallout4\n\n[OtherSection]\nfoo=bar\n";
      await writeFile(iniPath, initial, "utf8");

      const entry: MoIniCustomExecutable = {
        title: "Notepad",
        binary: "C:\\Windows\\System32\\notepad.exe",
        arguments: "",
        workingDirectory: "C:\\Windows\\System32",
        steamAppID: "",
        ownicon: false,
        hide: false,
      };

      const newText = _rewriteCustomExecutables(initial, undefined, [entry]);
      await writeFile(iniPath, newText, "utf8");

      // 1. Raw bytes on disk: forward-slash form, no leftover \W or \S escapes.
      const onDisk = await readFile(iniPath, "utf8");
      expect(onDisk).toContain("1\\binary=C:/Windows/System32/notepad.exe");
      expect(onDisk).toContain("1\\workingDirectory=C:/Windows/System32");
      expect(onDisk).not.toContain("C:\\Windows");
      expect(onDisk).not.toContain("C:indows");

      // 2. Verbatim preservation of unrelated sections.
      expect(onDisk).toContain("[General]");
      expect(onDisk).toContain("[OtherSection]");
      expect(onDisk).toContain("foo=bar");

      // 3. Round-trip through our own reader: forward-slash form parses,
      //    binary is a usable Windows path (drive letter + components).
      const ini = await readMoIni(iniPath);
      expect(ini.customExecutables).toHaveLength(1);
      expect(ini.customExecutables[0].title).toBe("Notepad");
      expect(ini.customExecutables[0].binary).toBe("C:/Windows/System32/notepad.exe");
      expect(ini.customExecutables[0].workingDirectory).toBe("C:/Windows/System32");
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("arguments containing embedded Windows path literal round-trip verbatim", async () => {
    const dir = await mkdtemp(join(tmpdir(), "mo-cfg-exec-args-"));
    const iniPath = join(dir, "ModOrganizer.ini");
    try {
      const initial = "[General]\ngame=fallout4\n";
      await writeFile(iniPath, initial, "utf8");

      const entry: MoIniCustomExecutable = {
        title: "xEdit FO4",
        binary: "D:/Tools/xEdit/xEdit.exe",
        arguments: '-fo4 -D:"D:\\Games\\Fallout 4\\Data"',
        workingDirectory: "D:/Tools/xEdit",
        steamAppID: "",
        ownicon: false,
        hide: false,
      };

      const newText = _rewriteCustomExecutables(initial, undefined, [entry]);
      const onDisk = newText;

      // arguments preserved verbatim — backslashes inside the quoted path
      // must NOT be touched.
      expect(onDisk).toContain(
        '1\\arguments=-fo4 -D:"D:\\Games\\Fallout 4\\Data"',
      );
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});
