import { describe, it, expect } from "vitest";
import { mkdtemp, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { loadConfig } from "../src/config.js";

describe("loadConfig", () => {
  it("reads BGS_MO2_ROOT and .mo2-mcp.json", async () => {
    const root = await mkdtemp(join(tmpdir(), "mo2-test-"));
    await writeFile(
      join(root, ".mo2-mcp.json"),
      JSON.stringify({
        permission_ceiling: "metadata-editable",
        allowed_profiles: ["Default", "Modding"],
      }),
    );

    const cfg = await loadConfig({ mo2Root: root });

    expect(cfg.mo2Root).toBe(root);
    expect(cfg.permissionCeiling).toBe("metadata-editable");
    expect(cfg.allowedProfiles).toEqual(["Default", "Modding"]);
    expect(cfg.snapshotRoot).toBe(join(root, ".mo2-mcp", "snapshots"));
    expect(cfg.auditRoot).toBe(join(root, ".mo2-mcp", "audit"));
    expect(cfg.deny).toEqual(["Stock Game/Data/**"]);
  });

  it("defaults to metadata-editable when .mo2-mcp.json missing", async () => {
    const root = await mkdtemp(join(tmpdir(), "mo2-test-"));
    const cfg = await loadConfig({ mo2Root: root });
    expect(cfg.permissionCeiling).toBe("metadata-editable");
    expect(cfg.allowedProfiles).toEqual(["Default"]);
    expect(cfg.deny).toEqual(["Stock Game/Data/**"]);
  });

  it("rejects empty mo2Root", async () => {
    await expect(loadConfig({ mo2Root: "" })).rejects.toThrow(/BGS_MO2_ROOT/);
  });

  it("accepts read-only ceiling", async () => {
    const root = await mkdtemp(join(tmpdir(), "mo2-test-"));
    await writeFile(
      join(root, ".mo2-mcp.json"),
      JSON.stringify({ permission_ceiling: "read-only" }),
    );

    const cfg = await loadConfig({ mo2Root: root });
    expect(cfg.permissionCeiling).toBe("read-only");
  });

  it("rejects invalid ceiling value", async () => {
    const root = await mkdtemp(join(tmpdir(), "mo2-test-"));
    await writeFile(
      join(root, ".mo2-mcp.json"),
      JSON.stringify({ permission_ceiling: "no-such-tier" }),
    );

    await expect(loadConfig({ mo2Root: root })).rejects.toThrow();
  });

  it("rejects unknown config fields (strict schema)", async () => {
    const root = await mkdtemp(join(tmpdir(), "mo2-test-"));
    await writeFile(
      join(root, ".mo2-mcp.json"),
      JSON.stringify({ permission_ceiling: "read-only", unknown_field: 42 }),
    );

    await expect(loadConfig({ mo2Root: root })).rejects.toThrow();
  });
});
