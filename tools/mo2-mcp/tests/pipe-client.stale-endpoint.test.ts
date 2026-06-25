/**
 * BUG-14 BUG-A (issue #14) — stale broker pipe after MO2 process restart.
 *
 * Reproduction shape from the issue:
 *   1. Start MO2 (PID A). Broker publishes endpoint.json with pipe name
 *      `mo2-control-plane-<A>`. PipeClient.discoverAndConnect caches it.
 *   2. Close MO2. Reopen MO2 (PID B). Broker rewrites endpoint.json with
 *      `mo2-control-plane-<B>`. Old pipe is gone.
 *   3. Without rebinding, every PipeClient.call hits the cached old pipe,
 *      fails with `ENOENT \\.\pipe\mo2-control-plane-<A>`.
 *
 * Fix: PipeClient.call() calls `_maybeRefreshStaleEndpoint()` before
 * `_rawCall`. That method re-reads endpoint.json (cheap local file read);
 * if the published pipe name differs from the cached `pipeName`, it
 * transparently swaps in the new pipe name. The next `_rawCall` connects
 * to the live broker instead of the dead one.
 *
 * These tests exercise the refresh helper directly using real fs (no node:fs
 * module mock) so the substrate matches production behavior.
 */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { PipeClient } from "../src/pipe-client.js";

async function _writeEndpointJson(
  mo2Root: string,
  endpoint: string,
  pid: number,
): Promise<void> {
  const dir = join(mo2Root, "plugins", "Mo2AgentControl", "bootstrap", "runtime");
  await mkdir(dir, { recursive: true });
  await writeFile(
    join(dir, "endpoint.json"),
    JSON.stringify({ endpoint, pid }),
    "utf8",
  );
}

describe("PipeClient._maybeRefreshStaleEndpoint (BUG-14 BUG-A)", () => {
  let mo2Root: string;

  beforeEach(async () => {
    mo2Root = await mkdtemp(join(tmpdir(), "mo2-stale-pipe-"));
  });

  afterEach(async () => {
    await rm(mo2Root, { recursive: true, force: true });
  });

  it("no-op when mo2Root is unset (one-off PipeClient usage)", async () => {
    const client = new PipeClient();
    // Force a cached pipeName without going through discoverAndConnect so we
    // exercise the early-return branch.
    (client as unknown as { pipeName: string }).pipeName = "some-pipe-name";
    await (client as unknown as { _maybeRefreshStaleEndpoint(): Promise<void> })._maybeRefreshStaleEndpoint();
    expect((client as unknown as { pipeName: string }).pipeName).toBe("some-pipe-name");
  });

  it("no-op when endpoint.json is absent (MO2 closed mid-call)", async () => {
    const client = new PipeClient();
    (client as unknown as { pipeName: string; mo2Root: string }).pipeName = "mo2-control-plane-89072";
    (client as unknown as { pipeName: string; mo2Root: string }).mo2Root = mo2Root;
    // No endpoint.json written.
    await (client as unknown as { _maybeRefreshStaleEndpoint(): Promise<void> })._maybeRefreshStaleEndpoint();
    // pipeName should remain unchanged; the next _rawCall will fail and
    // L1/L2 enrichment will report the absent endpoint.
    expect((client as unknown as { pipeName: string }).pipeName).toBe("mo2-control-plane-89072");
  });

  it("no-op when endpoint.json reports the SAME pipeName (MO2 still on original PID)", async () => {
    await _writeEndpointJson(mo2Root, "mo2-control-plane-89072", 89072);
    const client = new PipeClient();
    (client as unknown as { pipeName: string; mo2Root: string }).pipeName = "mo2-control-plane-89072";
    (client as unknown as { pipeName: string; mo2Root: string }).mo2Root = mo2Root;
    await (client as unknown as { _maybeRefreshStaleEndpoint(): Promise<void> })._maybeRefreshStaleEndpoint();
    expect((client as unknown as { pipeName: string }).pipeName).toBe("mo2-control-plane-89072");
  });

  it("auto-rebinds to the NEW pipeName when endpoint.json reports a different PID (MO2 was restarted)", async () => {
    // Initial state: PipeClient cached pipe from the original MO2 launch.
    const client = new PipeClient();
    (client as unknown as { pipeName: string; mo2Root: string }).pipeName = "mo2-control-plane-89072";
    (client as unknown as { pipeName: string; mo2Root: string }).mo2Root = mo2Root;

    // MO2 restarted: broker rewrote endpoint.json with a new PID.
    await _writeEndpointJson(mo2Root, "mo2-control-plane-44592", 44592);

    await (client as unknown as { _maybeRefreshStaleEndpoint(): Promise<void> })._maybeRefreshStaleEndpoint();

    // Cached pipeName now reflects the live broker. Next _rawCall will
    // connect to the right pipe instead of `connect ENOENT
    // \\.\pipe\mo2-control-plane-89072`.
    expect((client as unknown as { pipeName: string }).pipeName).toBe("mo2-control-plane-44592");
  });

  it("strips the \\\\.\\pipe\\ prefix when the broker publishes a fully-qualified endpoint", async () => {
    // Some endpoint.json writers may publish the full \\.\pipe\<name> form
    // rather than the bare pipe name. The refresh must normalize through
    // pipeNameOnly so the cached form stays consistent across both shapes.
    await _writeEndpointJson(
      mo2Root,
      "\\\\.\\pipe\\mo2-control-plane-44592",
      44592,
    );
    const client = new PipeClient();
    (client as unknown as { pipeName: string; mo2Root: string }).pipeName = "mo2-control-plane-89072";
    (client as unknown as { pipeName: string; mo2Root: string }).mo2Root = mo2Root;
    await (client as unknown as { _maybeRefreshStaleEndpoint(): Promise<void> })._maybeRefreshStaleEndpoint();
    expect((client as unknown as { pipeName: string }).pipeName).toBe("mo2-control-plane-44592");
  });
});
