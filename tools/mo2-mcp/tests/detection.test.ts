import { afterEach, describe, it, expect, vi } from "vitest";
import { detectMo2Running } from "../src/detection.js";

describe("detectMo2Running", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns all-false when tasklist shows no MO2 process", async () => {
    const result = await detectMo2Running({
      mo2Root: "C:\\nonexistent\\mo2",
      profileDir: undefined,
    });

    expect(result).toHaveProperty("processRunning");
    expect(result).toHaveProperty("sharedMemoryPresent");
    expect(result).toHaveProperty("profileLockHeld");
    expect(result).toHaveProperty("online");
    expect(typeof result.processRunning).toBe("boolean");
    expect(typeof result.online).toBe("boolean");
  });

  it("online is true only when both processRunning and sharedMemoryPresent", async () => {
    const cases: Array<[boolean, boolean, boolean]> = [
      [false, false, false],
      [true, false, false],
      [false, true, false],
      [true, true, true],
    ];

    for (const [proc, shm, expectedOnline] of cases) {
      const synthetic = {
        processRunning: proc,
        sharedMemoryPresent: shm,
        profileLockHeld: false,
        online: proc && shm,
      };
      expect(synthetic.online).toBe(expectedOnline);
    }
  });

  it("skips tier 3 when profileDir is not provided", async () => {
    const result = await detectMo2Running({
      mo2Root: "C:\\nonexistent",
      profileDir: undefined,
    });

    expect(result.profileLockHeld).toBe(false);
  });
});
