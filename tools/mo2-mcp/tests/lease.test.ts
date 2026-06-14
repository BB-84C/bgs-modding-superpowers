import { describe, it, expect } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import {
  fingerprintFile,
  fingerprintDir,
  computeLease,
  verifyLease,
} from "../src/lease.js";

describe("fingerprintFile", () => {
  it("returns content hash + size for existing file", async () => {
    const dir = await mkdtemp(join(tmpdir(), "lease-"));
    const f = join(dir, "test.txt");
    await writeFile(f, "hello world", "utf8");

    const fp = await fingerprintFile(f);

    expect(fp.path).toBe(f);
    expect(fp.kind).toBe("text-file");
    expect(fp.contentHash).toMatch(/^[0-9a-f]{64}$/);
    expect(fp.size).toBe(11);
  });

  it("returns 'missing' hash for non-existent file", async () => {
    const fp = await fingerprintFile("/nonexistent/path/file.txt");
    expect(fp.contentHash).toBe("missing");
    expect(fp.size).toBe(0);
  });

  it("different content → different hash", async () => {
    const dir = await mkdtemp(join(tmpdir(), "lease-"));
    const a = join(dir, "a.txt");
    const b = join(dir, "b.txt");
    await writeFile(a, "content A", "utf8");
    await writeFile(b, "content B", "utf8");

    const fa = await fingerprintFile(a);
    const fb = await fingerprintFile(b);
    expect(fa.contentHash).not.toBe(fb.contentHash);
  });
});

describe("fingerprintDir", () => {
  it("counts files + sums sizes recursively", async () => {
    const dir = await mkdtemp(join(tmpdir(), "lease-"));
    await writeFile(join(dir, "a.txt"), "hello", "utf8"); // 5 bytes
    await mkdir(join(dir, "sub"));
    await writeFile(join(dir, "sub", "b.txt"), "world!!", "utf8"); // 7 bytes

    const fp = await fingerprintDir(dir);
    expect(fp.fileCount).toBe(2);
    expect(fp.totalSize).toBe(12);
  });

  it("returns zero counts for non-existent dir", async () => {
    const fp = await fingerprintDir("/nonexistent/path/dir");
    expect(fp.fileCount).toBe(0);
    expect(fp.totalSize).toBe(0);
  });
});

describe("computeLease + verifyLease", () => {
  it("verify returns valid when nothing changed", async () => {
    const dir = await mkdtemp(join(tmpdir(), "lease-"));
    const f = join(dir, "data.txt");
    await writeFile(f, "stable", "utf8");

    const lease = await computeLease([{ path: f, kind: "text-file" }]);
    const result = await verifyLease(lease);

    expect(result.valid).toBe(true);
  });

  it("verify returns drift when file content changes", async () => {
    const dir = await mkdtemp(join(tmpdir(), "lease-"));
    const f = join(dir, "data.txt");
    await writeFile(f, "original", "utf8");

    const lease = await computeLease([{ path: f, kind: "text-file" }]);
    await writeFile(f, "mutated", "utf8");

    const result = await verifyLease(lease);
    expect(result.valid).toBe(false);
    if (!result.valid) {
      expect(result.drift).toHaveLength(1);
      expect(result.drift[0].path).toBe(f);
      expect(result.drift[0].planComponent.contentHash).not.toBe(
        result.drift[0].currentComponent.contentHash,
      );
    }
  });

  it("verify returns drift when dir file count changes", async () => {
    const dir = await mkdtemp(join(tmpdir(), "lease-"));
    const subdir = join(dir, "sub");
    await mkdir(subdir);
    await writeFile(join(subdir, "a.txt"), "A", "utf8");

    const lease = await computeLease([{ path: subdir, kind: "directory" }]);

    // Add a new file
    await writeFile(join(subdir, "b.txt"), "B", "utf8");

    const result = await verifyLease(lease);
    expect(result.valid).toBe(false);
  });

  it("lease token is deterministic given identical components", async () => {
    const dir = await mkdtemp(join(tmpdir(), "lease-"));
    const f = join(dir, "data.txt");
    await writeFile(f, "stable", "utf8");

    const a = await computeLease([{ path: f, kind: "text-file" }]);
    const b = await computeLease([{ path: f, kind: "text-file" }]);
    expect(a.token).toBe(b.token);
  });
});
