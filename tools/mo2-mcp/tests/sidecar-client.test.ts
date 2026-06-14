import { describe, it, expect } from "vitest";
import { SidecarClient } from "../src/sidecar-client.js";

describe("SidecarClient", () => {
  it("isReady returns false before start", () => {
    const client = new SidecarClient();
    expect(client.isReady()).toBe(false);
  });

  it("throws when call() invoked before start", async () => {
    const client = new SidecarClient();
    await expect(client.call("system.echo", {})).rejects.toThrow(/sidecar_not_ready/);
  });

  it("rejects with startup timeout when python missing", async () => {
    const client = new SidecarClient();
    await expect(
      client.start({
        pythonPath: "definitely-not-a-real-python-binary-xyz",
        modsRoot: "/tmp",
        game: "FALLOUT4",
      }),
    ).rejects.toThrow();
  });
});
