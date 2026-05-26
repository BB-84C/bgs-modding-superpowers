import { describe, it, expect, beforeEach } from "vitest";
import { mkdtempSync, readFileSync, existsSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createAuditLogger } from "../../src/audit.js";

describe("audit logger", () => {
  let dir: string;
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "xedit-mcp-audit-"));
  });

  it("writes one JSONL line per record under YYYY-MM-DD.jsonl", async () => {
    const logger = createAuditLogger({ baseDir: dir });
    await logger.append({
      tool: "xedit_session",
      argsHash: "abc123",
      decision: "ok",
      ok: true,
    });
    await logger.append({
      tool: "xedit_find_record",
      argsHash: "def456",
      decision: "refused",
      ok: false,
      code: "rule_LOAD001",
    });

    const today = new Date().toISOString().slice(0, 10);
    const filePath = join(dir, `${today}.jsonl`);
    expect(existsSync(filePath)).toBe(true);

    const lines = readFileSync(filePath, "utf8").trim().split("\n");
    expect(lines).toHaveLength(2);
    const first = JSON.parse(lines[0]);
    expect(first.tool).toBe("xedit_session");
    expect(first.ok).toBe(true);
    expect(typeof first.ts).toBe("string");
    const second = JSON.parse(lines[1]);
    expect(second.code).toBe("rule_LOAD001");
  });

  it("never throws on disk errors; surfaces via onError callback", async () => {
    // Make baseDir point at an existing FILE so mkdir-recursive fails with ENOTDIR
    // (and even if mkdir somehow succeeds, appendFile to file/<day>.jsonl fails).
    // This is cross-platform: a path component that exists as a file cannot be a directory parent on either Windows or POSIX.
    const parent = mkdtempSync(join(tmpdir(), "xedit-mcp-audit-bad-"));
    const fileAsDir = join(parent, "not-a-dir.txt");
    writeFileSync(fileAsDir, "");

    const errors: unknown[] = [];
    const logger = createAuditLogger({
      baseDir: fileAsDir,
      onError: (e) => errors.push(e),
    });
    await logger.append({ tool: "x", argsHash: "h", decision: "ok", ok: true });
    expect(errors.length).toBe(1);
  });
});
