import { describe, it, expect } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile, readdir, stat } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { SnapshotManager } from "../src/snapshot.js";

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

  it("records missing-file entries with empty backup path", async () => {
    const root = await mkdtemp(join(tmpdir(), "snap-"));
    const mgr = new SnapshotManager(root, "sess-1");

    const record = await mgr.snapshot("test", [join(root, "does-not-exist.txt")]);

    expect(record.files).toHaveLength(1);
    expect(record.files[0].backup).toBe("");
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

    const exists = await stat(target)
      .then(() => true)
      .catch(() => false);
    expect(exists).toBe(false);
  });

  it("throws snapshot_not_found for unknown snapshotId", async () => {
    const root = await mkdtemp(join(tmpdir(), "snap-"));
    const mgr = new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "sess-1");

    await expect(mgr.restore("nonexistent-uuid")).rejects.toThrow(/snapshot_not_found/);
  });
});
