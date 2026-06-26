import { afterEach, describe, expect, it, vi } from "vitest";
import { pollPluginWarnings } from "../src/plugin-warnings.js";
import type { PipeClient } from "../src/pipe-client.js";

function pipe(call: PipeClient["call"]): PipeClient {
  return {
    call,
    close: () => {},
    discoverAndConnect: async () => {},
    isConnected: () => true,
  } as unknown as PipeClient;
}

describe("pollPluginWarnings", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("maps successful broker response to camelCase fields", async () => {
    const client = pipe(async () => ({
      ok: true,
      result: {
        warnings: [
          {
            plugin: "SVF-Deadalus-Patch.esm",
            missing_masters: ["deadalus1.esm"],
            enabled_masters: ["ShipVendorFramework.esm"],
            declared_masters: ["ShipVendorFramework.esm", "deadalus1.esm"],
          },
        ],
        scanned_count: 2,
        enabled_count: 12,
      },
      error: null,
    }));

    await expect(pollPluginWarnings(client)).resolves.toEqual({
      warnings: [
        {
          plugin: "SVF-Deadalus-Patch.esm",
          missingMasters: ["deadalus1.esm"],
          enabledMasters: ["ShipVendorFramework.esm"],
          declaredMasters: ["ShipVendorFramework.esm", "deadalus1.esm"],
        },
      ],
      scannedCount: 2,
      enabledCount: 12,
    });
  });

  it("handles stale brokers with a sentinel and emits stderr only once", async () => {
    const stderr = vi.spyOn(process.stderr, "write").mockImplementation(() => true);
    const client = pipe(async () => ({
      ok: false,
      result: null,
      error: { code: "method_not_found", message: "Unsupported method: plugins.missing_masters" },
    }));

    const first = await pollPluginWarnings(client);
    const second = await pollPluginWarnings(client);

    expect(first).toEqual({
      warnings: [],
      scannedCount: 0,
      enabledCount: 0,
      pollFailed: "broker_stale_missing_masters_handler_not_deployed",
    });
    expect(second.pollFailed).toBe("broker_stale_missing_masters_handler_not_deployed");
    expect(stderr).toHaveBeenCalledTimes(1);
  });

  it("returns broker error messages as pollFailed", async () => {
    const client = pipe(async () => ({
      ok: false,
      result: null,
      error: { code: "pipe_call_timeout", message: "MO2 did not answer" },
    }));

    await expect(pollPluginWarnings(client)).resolves.toEqual({
      warnings: [],
      scannedCount: 0,
      enabledCount: 0,
      pollFailed: "MO2 did not answer",
    });
  });

  it("returns thrown exceptions as pollFailed", async () => {
    const client = pipe(async () => {
      throw new Error("radiation leak in pipe room");
    });

    await expect(pollPluginWarnings(client)).resolves.toEqual({
      warnings: [],
      scannedCount: 0,
      enabledCount: 0,
      pollFailed: "radiation leak in pipe room",
    });
  });

  it("passes a names filter through to broker call args", async () => {
    const call = vi.fn(async () => ({ ok: true, result: { warnings: [] }, error: null }));
    const client = pipe(call as PipeClient["call"]);

    await pollPluginWarnings(client, ["plugin.esm"]);

    expect(call).toHaveBeenCalledWith("plugins.missing_masters", { names: ["plugin.esm"] });
  });
});
