import { describe, it, expect } from "vitest";
import { upsertIniValue } from "../src/ini-helpers.js";

describe("upsertIniValue", () => {
  it("updates existing key in existing section", () => {
    const before = "[General]\nversion=1.0\nname=foo\n";
    const after = upsertIniValue(before, "General", "version", "2.0");
    expect(after).toContain("version=2.0");
    expect(after).toContain("name=foo");
    expect(after).not.toContain("version=1.0");
  });

  it("adds new key to existing section", () => {
    const before = "[General]\nversion=1.0\n";
    const after = upsertIniValue(before, "General", "notes", '"hello"');
    expect(after).toContain('notes="hello"');
    expect(after).toContain("version=1.0");
  });

  it("appends new section + key", () => {
    const before = "[General]\nversion=1.0\n";
    const after = upsertIniValue(before, "Nexus", "nexusID", "42");
    expect(after).toContain("[Nexus]\nnexusID=42");
    expect(after).toContain("[General]");
  });

  it("creates section + key from empty text", () => {
    const after = upsertIniValue("", "General", "key", "value");
    expect(after).toContain("[General]\nkey=value");
  });
});
