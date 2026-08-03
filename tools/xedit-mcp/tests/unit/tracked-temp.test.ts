import { describe, expect, it } from "vitest";
import { existsSync } from "node:fs";
import { cleanupTrackedTempDirs, createTrackedTempDirSync } from "./tracked-temp.js";

describe("xEdit MCP tracked test temp directories", () => {
  it("removes all explicitly registered audit directories", () => {
    const first = createTrackedTempDirSync("xedit-mcp-tracked-");
    const second = createTrackedTempDirSync("xedit-mcp-tracked-failure-");

    expect(existsSync(first)).toBe(true);
    expect(existsSync(second)).toBe(true);

    cleanupTrackedTempDirs();

    expect(existsSync(first)).toBe(false);
    expect(existsSync(second)).toBe(false);
  });
});
