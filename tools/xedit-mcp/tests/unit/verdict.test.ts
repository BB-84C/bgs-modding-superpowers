import { describe, it, expect } from "vitest";
import { mapVerdict } from "../../src/verdict.js";

describe("verdict.mapVerdict", () => {
  it("maps caXxx enum values from the live daemon", () => {
    expect(mapVerdict("caUnknown")).toBe("no_conflict");
    expect(mapVerdict("caOnlyOne")).toBe("no_conflict");
    expect(mapVerdict("caNoConflict")).toBe("no_conflict");
    expect(mapVerdict("caITM")).toBe("itm");
    expect(mapVerdict("caITPO")).toBe("itpo");
    expect(mapVerdict("caOverride")).toBe("minor");
    expect(mapVerdict("caConflictBenign")).toBe("minor");
    expect(mapVerdict("caConflict")).toBe("minor");
    expect(mapVerdict("caConflictCritical")).toBe("breaking");
  });

  it("recognizes legacy flat string statuses (unit-test mock vocab)", () => {
    expect(mapVerdict("no_conflict")).toBe("no_conflict");
    expect(mapVerdict("no conflict")).toBe("no_conflict");
    expect(mapVerdict("conflict_critical")).toBe("breaking");
    expect(mapVerdict("ITPO")).toBe("itpo");
    expect(mapVerdict("ITM")).toBe("itm");
  });

  it("falls back to minor on unknown conflict-ish status", () => {
    expect(mapVerdict("conflict")).toBe("minor");
    expect(mapVerdict("something-weird")).toBe("minor");
  });
});
