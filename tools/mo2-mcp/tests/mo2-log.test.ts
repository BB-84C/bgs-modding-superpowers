import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { copyFile, mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

import { tailMo2Log } from "../src/mo2-log.js";

const FIXTURE_PATH = join(dirname(fileURLToPath(import.meta.url)), "fixtures", "mo2.log.fixture");

let tempRoot: string;

async function seedLogFromFixture(): Promise<string> {
  const logDir = join(tempRoot, "logs");
  await mkdir(logDir, { recursive: true });
  const target = join(logDir, "mo2.log");
  await copyFile(FIXTURE_PATH, target);
  return target;
}

async function seedLogFromString(text: string): Promise<string> {
  const logDir = join(tempRoot, "logs");
  await mkdir(logDir, { recursive: true });
  const target = join(logDir, "mo2.log");
  await writeFile(target, text, "utf8");
  return target;
}

describe("tailMo2Log", () => {
  beforeEach(async () => {
    tempRoot = await mkdtemp(join(tmpdir(), "mo2-log-test-"));
  });

  afterEach(async () => {
    await rm(tempRoot, { recursive: true, force: true });
  });

  it("returns all non-empty lines when no sinceTs is set", async () => {
    const target = await seedLogFromFixture();
    const result = await tailMo2Log(tempRoot);
    expect(result.logPath).toBe(target);
    expect(result.truncated).toBe(false);
    // Fixture has 7 timestamped lines + 2 continuation/stack lines = 9
    expect(result.lines.length).toBe(9);
    expect(result.lines[0]).toContain("starting up");
    expect(result.lines[result.lines.length - 1]).toContain("shutting down");
  });

  it("filters lines by sinceTs (keeps newer timestamped lines plus continuation lines)", async () => {
    await seedLogFromFixture();
    // Pick a sinceTs at 02:58:58.500 — keeps timestamped lines >= that mark
    // and ALL continuation (non-timestamped) lines per the design.
    const result = await tailMo2Log(tempRoot, {
      sinceTs: new Date("2026-06-17T02:58:58.500Z"),
    });
    // Should include: error message 2 (02:58:58.500), another info (02:58:59.200),
    // Cannot launch program (02:59:00.000), shutting down (02:59:01.500) = 4 timestamped,
    // plus 2 continuation lines that have no timestamp = 6 lines total.
    expect(result.lines.length).toBe(6);
    expect(result.lines.some((line) => line.includes("error message 2"))).toBe(true);
    expect(result.lines.some((line) => line.includes("Cannot launch program"))).toBe(true);
    // Old timestamped lines are gone.
    expect(result.lines.some((line) => line.includes("starting up"))).toBe(false);
    expect(result.lines.some((line) => line.includes("error message 1"))).toBe(false);
  });

  it("keeps continuation (non-timestamped) lines through the sinceTs filter", async () => {
    const text = [
      "[2026-06-17 03:00:00.000 I] before",
      "[2026-06-17 03:00:05.000 E] error",
      "  at handler.cpp:123",
      "  at dispatch.cpp:456",
      "[2026-06-17 03:00:10.000 I] after",
    ].join("\n");
    await seedLogFromString(text);
    const result = await tailMo2Log(tempRoot, {
      sinceTs: new Date("2026-06-17T03:00:05.000Z"),
    });
    // error + 2 continuation + after = 4
    expect(result.lines.length).toBe(4);
    expect(result.lines[1]).toContain("at handler.cpp:123");
    expect(result.lines[2]).toContain("at dispatch.cpp:456");
  });

  it("respects maxLines and reports truncated=true when exceeded", async () => {
    await seedLogFromFixture();
    const result = await tailMo2Log(tempRoot, { maxLines: 2 });
    expect(result.lines.length).toBe(2);
    expect(result.truncated).toBe(true);
    // Tail keeps the LAST maxLines entries.
    expect(result.lines[result.lines.length - 1]).toContain("shutting down");
  });

  it("returns empty result with the computed logPath when the log file is missing", async () => {
    const result = await tailMo2Log(tempRoot);
    expect(result.lines).toEqual([]);
    expect(result.truncated).toBe(false);
    expect(result.logPath).toBe(join(tempRoot, "logs", "mo2.log"));
  });

  it("returns empty result when the mo2Root itself does not exist", async () => {
    const result = await tailMo2Log("C:\\definitely-not-a-real-path-xyz123");
    expect(result.lines).toEqual([]);
    expect(result.truncated).toBe(false);
    expect(result.logPath).toContain("mo2.log");
  });

  it("handles CRLF line endings as well as LF", async () => {
    const text = [
      "[2026-06-17 03:00:00.000 I] line a",
      "[2026-06-17 03:00:00.500 I] line b",
      "[2026-06-17 03:00:01.000 I] line c",
    ].join("\r\n");
    await seedLogFromString(text);
    const result = await tailMo2Log(tempRoot);
    expect(result.lines.length).toBe(3);
    expect(result.lines[0]).toContain("line a");
  });

  it("returns an empty (but well-formed) result for an empty log file", async () => {
    await seedLogFromString("");
    const result = await tailMo2Log(tempRoot);
    expect(result.lines).toEqual([]);
    expect(result.truncated).toBe(false);
  });

  it("ignores lines older than sinceTs and keeps only newer ones", async () => {
    const text = [
      "[2026-06-17 03:00:00.000 I] way old",
      "[2026-06-17 03:00:01.000 I] old",
      "[2026-06-17 03:05:00.000 E] new",
    ].join("\n");
    await seedLogFromString(text);
    const result = await tailMo2Log(tempRoot, {
      sinceTs: new Date("2026-06-17T03:04:00.000Z"),
    });
    expect(result.lines.length).toBe(1);
    expect(result.lines[0]).toContain("new");
  });

  it("only reads the trailing maxBytes window of a large log", async () => {
    const padding = "[2026-06-17 03:00:00.000 I] padding line\n".repeat(1000);
    const tail = "[2026-06-17 03:05:00.000 I] target line\n";
    await seedLogFromString(padding + tail);
    const result = await tailMo2Log(tempRoot, { maxBytes: 200 });
    // The 200-byte tail should contain the target line and ONLY a small slice
    // of padding lines (much fewer than 1000). The partial first line is dropped.
    expect(result.lines.some((line) => line.includes("target line"))).toBe(true);
    expect(result.lines.length).toBeLessThan(20);
  });
});
