import { afterEach, describe, expect, it } from "vitest";
import { existsSync } from "node:fs";
import {
  cleanupTrackedTempDirs,
  createTrackedTempDir,
  trackedTempDirs,
} from "./tracked-temp.js";

describe("tracked test temp directories", () => {
  afterEach(async () => {
    await cleanupTrackedTempDirs();
  });

  it("removes every directory it registers", async () => {
    const first = await createTrackedTempDir("mo2-mcp-temp-helper-");
    const second = await createTrackedTempDir("mo2-mcp-temp-helper-failure-");

    expect(trackedTempDirs()).toEqual(expect.arrayContaining([first, second]));
    expect(existsSync(first)).toBe(true);
    expect(existsSync(second)).toBe(true);

    await cleanupTrackedTempDirs();

    expect(existsSync(first)).toBe(false);
    expect(existsSync(second)).toBe(false);
    expect(trackedTempDirs()).toEqual([]);
  });

  it("cleans registered directories when a fixture path throws", async () => {
    let failedFixture: string | undefined;
    try {
      failedFixture = await createTrackedTempDir("mo2-mcp-temp-helper-throw-");
      throw new Error("fixture setup failed");
    } catch (error) {
      expect(error).toHaveProperty("message", "fixture setup failed");
    } finally {
      await cleanupTrackedTempDirs();
    }

    expect(failedFixture).toBeDefined();
    expect(existsSync(failedFixture!)).toBe(false);
  });

  it("registers fixtures through the explicit shared constructor", async () => {
    const legacyFixture = await createTrackedTempDir("mo2-mcp-explicit-fixture-");

    expect(trackedTempDirs()).toContain(legacyFixture);
    await cleanupTrackedTempDirs();
    expect(existsSync(legacyFixture)).toBe(false);
  });
});
