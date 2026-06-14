import { describe, it, expect } from "vitest";
import { mkdtemp, readFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { AuditLogger, hashArgs } from "../src/audit.js";

describe("AuditLogger", () => {
  it("creates audit dir + appends JSONL records", async () => {
    const root = await mkdtemp(join(tmpdir(), "audit-"));
    const auditRoot = join(root, "subdir-not-yet-existing");
    const logger = new AuditLogger(auditRoot, "sess-abc");

    await logger.log({
      ts: new Date().toISOString(),
      sessionId: "sess-abc",
      tool: "mo2_status",
      argsHash: "abc123",
      decision: "ok",
      durationMs: 42,
    });

    const files = await readdir(auditRoot);
    expect(files).toHaveLength(1);
    expect(files[0]).toMatch(/^sess-abc-\d{4}-\d{2}-\d{2}\.jsonl$/);

    const content = await readFile(join(auditRoot, files[0]), "utf8");
    const lines = content.trim().split("\n");
    expect(lines).toHaveLength(1);
    const rec = JSON.parse(lines[0]);
    expect(rec.tool).toBe("mo2_status");
    expect(rec.decision).toBe("ok");
  });

  it("appends multiple records to same file", async () => {
    const root = await mkdtemp(join(tmpdir(), "audit-"));
    const logger = new AuditLogger(root, "sess-1");
    const now = new Date().toISOString();

    await logger.log({
      ts: now,
      sessionId: "sess-1",
      tool: "mo2_modlist",
      argsHash: "h1",
      decision: "ok",
      durationMs: 10,
    });
    await logger.log({
      ts: now,
      sessionId: "sess-1",
      tool: "mo2_toggle_mod",
      argsHash: "h2",
      mode: "plan",
      decision: "plan_generated",
      durationMs: 25,
      planId: "p-1",
    });

    const files = await readdir(root);
    const content = await readFile(join(root, files[0]), "utf8");
    const lines = content.trim().split("\n");
    expect(lines).toHaveLength(2);
    expect(JSON.parse(lines[1]).planId).toBe("p-1");
  });

  it("never throws even if write fails (logs to stderr)", async () => {
    const logger = new AuditLogger("Z:\\nonexistent-drive-xyz\\audit", "sess");
    await expect(
      logger.log({
        ts: new Date().toISOString(),
        sessionId: "sess",
        tool: "mo2_status",
        argsHash: "h",
        decision: "ok",
        durationMs: 1,
      }),
    ).resolves.toBeUndefined();
  });

  it("uses different files for different sessions", async () => {
    const root = await mkdtemp(join(tmpdir(), "audit-"));
    const a = new AuditLogger(root, "sess-A");
    const b = new AuditLogger(root, "sess-B");
    const now = new Date().toISOString();

    await a.log({ ts: now, sessionId: "sess-A", tool: "x", argsHash: "h", decision: "ok", durationMs: 1 });
    await b.log({ ts: now, sessionId: "sess-B", tool: "y", argsHash: "h", decision: "ok", durationMs: 1 });

    const files = await readdir(root);
    expect(files).toHaveLength(2);
    expect(files.some((f) => f.startsWith("sess-A-"))).toBe(true);
    expect(files.some((f) => f.startsWith("sess-B-"))).toBe(true);
  });
});

describe("hashArgs", () => {
  it("returns 16 hex chars", () => {
    const h = hashArgs({ name: "ModA", priority: 5 });
    expect(h).toMatch(/^[0-9a-f]{16}$/);
  });

  it("is deterministic", () => {
    expect(hashArgs({ x: 1 })).toBe(hashArgs({ x: 1 }));
  });

  it("differentiates different args", () => {
    expect(hashArgs({ x: 1 })).not.toBe(hashArgs({ x: 2 }));
  });

  it("handles null and undefined", () => {
    expect(hashArgs(null)).toMatch(/^[0-9a-f]{16}$/);
    expect(hashArgs(undefined)).toMatch(/^[0-9a-f]{16}$/);
  });
});
