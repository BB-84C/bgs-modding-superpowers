import { describe, it, expect } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile, readdir, stat, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { SnapshotManager } from "../src/snapshot.js";

async function exists(path: string): Promise<boolean> {
  return stat(path)
    .then(() => true)
    .catch(() => false);
}

describe("SnapshotManager.snapshot", () => {
  it("creates snapshot dir + manifest + copies files", async () => {
    const root = await mkdtemp(join(tmpdir(), "snap-"));
    const snapRoot = join(root, ".mo2-mcp", "snapshots");
    const mgr = new SnapshotManager(snapRoot, "sess-1");

    const srcDir = join(root, "profiles", "Default");
    await mkdir(srcDir, { recursive: true });
    const modlist = join(srcDir, "modlist.txt");
    await writeFile(modlist, "+ModA\n+ModB\n", "utf8");

    const record = await mgr.snapshot("mo2_toggle_mod", [modlist]);

    expect(record.snapshotId).toMatch(/^[0-9a-f-]+$/);
    expect(record.tool).toBe("mo2_toggle_mod");
    expect(record.files).toHaveLength(1);
    expect(record.files[0].source).toBe(modlist);
    expect(record.files[0].backup).toBeTruthy();

    const sessionDir = join(snapRoot, "sess-1");
    const dirs = await readdir(sessionDir);
    expect(dirs).toHaveLength(1);
    const manifestText = await readFile(join(sessionDir, dirs[0], "manifest.json"), "utf8");
    const parsed = JSON.parse(manifestText);
    expect(parsed.snapshotId).toBe(record.snapshotId);

    const backupContent = await readFile(record.files[0].backup, "utf8");
    expect(backupContent).toBe("+ModA\n+ModB\n");
  });

  it("snapshots multiple files into one record", async () => {
    const root = await mkdtemp(join(tmpdir(), "snap-"));
    const mgr = new SnapshotManager(root, "sess-1");

    const a = join(root, "a.txt");
    const b = join(root, "b.txt");
    await writeFile(a, "A", "utf8");
    await writeFile(b, "B", "utf8");

    const record = await mgr.snapshot("test", [a, b]);
    expect(record.files).toHaveLength(2);
  });

  it("records missing-file entries as absent sources", async () => {
    const root = await mkdtemp(join(tmpdir(), "snap-"));
    const mgr = new SnapshotManager(root, "sess-1");

    const record = await mgr.snapshot("test", [join(root, "does-not-exist.txt")]);

    expect(record.files).toHaveLength(1);
    expect(record.files[0].kind).toBe("absent");
    expect(record.files[0].backup).toBe("");
  });

  it("snapshots existing directories recursively", async () => {
    const root = await mkdtemp(join(tmpdir(), "snap-"));
    const mgr = new SnapshotManager(root, "sess-1");
    const dir = join(root, "mods", "Dir Mod");
    await mkdir(join(dir, "Data", "Scripts"), { recursive: true });
    await writeFile(join(dir, "Data", "Scripts", "foo.pex"), "compiled", "utf8");

    const record = await mgr.snapshot("test", [dir]);

    expect(record.files[0].kind).toBe("directory");
    expect(await readFile(join(record.files[0].backup, "Data", "Scripts", "foo.pex"), "utf8")).toBe("compiled");
  });
});

describe("SnapshotManager.restore", () => {
  it("restores file content from snapshot", async () => {
    const root = await mkdtemp(join(tmpdir(), "snap-"));
    const mgr = new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "sess-1");

    const target = join(root, "data.txt");
    await writeFile(target, "original\n", "utf8");
    const record = await mgr.snapshot("test", [target]);

    await writeFile(target, "MUTATED\n", "utf8");

    const result = await mgr.restore(record.snapshotId);
    expect(result.restored).toEqual([target]);
    expect(result.failed).toEqual([]);
    expect(await readFile(target, "utf8")).toBe("original\n");
  });

  it("deletes source file when snapshot recorded it as non-existent", async () => {
    const root = await mkdtemp(join(tmpdir(), "snap-"));
    const mgr = new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "sess-1");

    const target = join(root, "to-create.txt");
    const record = await mgr.snapshot("test", [target]);
    await writeFile(target, "data", "utf8");

    const result = await mgr.restore(record.snapshotId);
    expect(result.restored).toContain(target);

    expect(await exists(target)).toBe(false);
  });

  it("removes a newly-created directory when snapshot recorded it as absent", async () => {
    const root = await mkdtemp(join(tmpdir(), "snap-"));
    const mgr = new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "sess-1");

    const target = join(root, "profiles", "New Profile");
    const record = await mgr.snapshot("test", [target]);
    await mkdir(join(target, "nested"), { recursive: true });
    await writeFile(join(target, "nested", "modlist.txt"), "+Created\n", "utf8");

    const result = await mgr.restore(record.snapshotId);
    expect(result.restored).toContain(target);
    expect(result.failed).toEqual([]);
    expect(await exists(target)).toBe(false);
  });

  it("restores an existing directory by replacing the mutated tree", async () => {
    const root = await mkdtemp(join(tmpdir(), "snap-"));
    const mgr = new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "sess-1");

    const target = join(root, "mods", "Existing Dir");
    await mkdir(join(target, "Data", "Meshes"), { recursive: true });
    await writeFile(join(target, "Data", "Meshes", "original.nif"), "original", "utf8");
    const record = await mgr.snapshot("test", [target]);

    await rm(join(target, "Data"), { recursive: true, force: true });
    await mkdir(join(target, "extra"), { recursive: true });
    await writeFile(join(target, "extra", "new.txt"), "new", "utf8");

    const result = await mgr.restore(record.snapshotId);
    expect(result.restored).toEqual([target]);
    expect(result.failed).toEqual([]);
    expect(await readFile(join(target, "Data", "Meshes", "original.nif"), "utf8")).toBe("original");
    expect(await exists(join(target, "extra", "new.txt"))).toBe(false);
  });

  it("throws snapshot_not_found for unknown snapshotId", async () => {
    const root = await mkdtemp(join(tmpdir(), "snap-"));
    const mgr = new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "sess-1");

    await expect(mgr.restore("nonexistent-uuid")).rejects.toThrow(/snapshot_not_found/);
  });
});
