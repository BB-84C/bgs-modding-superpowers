import { EventEmitter } from "node:events";
import { beforeEach, describe, expect, it, vi } from "vitest";

type FakeProc = EventEmitter & {
  stdout: EventEmitter;
  stderr: EventEmitter;
  stdin: { write: ReturnType<typeof vi.fn>; end: ReturnType<typeof vi.fn> };
  exitCode: number | null;
  kill: ReturnType<typeof vi.fn>;
};

const spawnMock = vi.hoisted(() => vi.fn());
const procs = vi.hoisted(() => [] as FakeProc[]);

vi.mock("node:child_process", () => ({
  spawn: spawnMock,
}));

function makeProc(index: number): FakeProc {
  const proc = new EventEmitter() as FakeProc;
  proc.stdout = new EventEmitter();
  proc.stderr = new EventEmitter();
  proc.exitCode = null;
  proc.kill = vi.fn();
  proc.stdin = {
    end: vi.fn(),
    write: vi.fn((chunk: string) => {
      const request = JSON.parse(chunk.trim()) as { id: number };
      queueMicrotask(() => {
        proc.stdout.emit("data", `${JSON.stringify({ jsonrpc: "2.0", id: request.id, result: { proc: index } })}\n`);
      });
      return true;
    }),
  };
  return proc;
}

async function waitFor(condition: () => boolean): Promise<void> {
  for (let i = 0; i < 20; i++) {
    if (condition()) return;
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  throw new Error("condition not met");
}

describe("SidecarClient auto-restart", () => {
  beforeEach(() => {
    procs.length = 0;
    spawnMock.mockReset();
    spawnMock.mockImplementation(() => {
      const proc = makeProc(procs.length);
      procs.push(proc);
      return proc;
    });
  });

  it("restarts after child exit and routes later calls to the replacement sidecar", async () => {
    const { SidecarClient } = await import("../src/sidecar-client.js");
    const client = new SidecarClient();
    const start = client.start({ modsRoot: "/tmp/mods", game: "FALLOUT4" });
    procs[0].stdout.emit("data", '{"ready":true}\n');
    await start;

    procs[0].emit("exit", 1, null);
    await waitFor(() => procs.length === 2);
    procs[1].stdout.emit("data", '{"ready":true}\n');
    await waitFor(() => client.isReady());

    await expect(client.call("system.echo", {})).resolves.toEqual({ proc: 1 });
    expect(spawnMock).toHaveBeenCalledTimes(2);
  });

  it("caps automatic restarts at three attempts", async () => {
    const { SidecarClient } = await import("../src/sidecar-client.js");
    const client = new SidecarClient();
    const start = client.start({ modsRoot: "/tmp/mods", game: "FALLOUT4" });
    procs[0].stdout.emit("data", '{"ready":true}\n');
    await start;

    for (let i = 0; i < 4; i++) {
      procs[i].emit("exit", 1, null);
      if (i < 3) {
        await waitFor(() => procs.length === i + 2);
        procs[i + 1].stdout.emit("data", '{"ready":true}\n');
      }
    }

    expect(spawnMock).toHaveBeenCalledTimes(4);
    await expect(client.call("system.echo", {})).rejects.toThrow(/sidecar_not_ready/);
  });
});
