import { describe, it, expect } from "vitest";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";

describe("daemon adapter (mock contract)", () => {
  it("returns the raw native ok envelope for a known command", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4", dataPath: "C:/x" }),
    });
    const res = await adapter.call({ command: "system.describe", args: {} });
    expect(res.ok).toBe(true);
    if (!res.ok) throw new Error("expected ok");
    expect((res.result as { gameMode: string }).gameMode).toBe("Fallout4");
  });

  it("returns a native error envelope for an unknown command", async () => {
    const adapter = makeMockAdapter({});
    const res = await adapter.call({ command: "nope.nope", args: {} });
    expect(res.ok).toBe(false);
    if (res.ok) throw new Error("expected error");
    expect(res.error.code).toBe("unknown_command");
  });

  describe("createPowershellAdapter validation", () => {
    it("throws on non-positive timeoutSeconds at construction time", async () => {
      const { createPowershellAdapter } = await import("../../src/daemon-adapter.js");
      expect(() =>
        createPowershellAdapter({
          clientScript: "x",
          pid: 1,
          timeoutSeconds: 0,
        }),
      ).toThrow(/Invalid timeoutSeconds/);
      expect(() =>
        createPowershellAdapter({
          clientScript: "x",
          pid: 1,
          timeoutSeconds: -5,
        }),
      ).toThrow(/Invalid timeoutSeconds/);
      expect(() =>
        createPowershellAdapter({
          clientScript: "x",
          pid: 1,
          timeoutSeconds: Number.POSITIVE_INFINITY,
        }),
      ).toThrow(/Invalid timeoutSeconds/);
    });

    it("accepts a valid timeoutSeconds and omitted default", async () => {
      const { createPowershellAdapter } = await import("../../src/daemon-adapter.js");
      expect(() => createPowershellAdapter({ clientScript: "x", pid: 1 })).not.toThrow();
      expect(() =>
        createPowershellAdapter({
          clientScript: "x",
          pid: 1,
          timeoutSeconds: 60,
        }),
      ).not.toThrow();
    });
  });
});
