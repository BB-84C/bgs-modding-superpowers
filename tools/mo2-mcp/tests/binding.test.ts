import { describe, expect, it } from "vitest";
import { join } from "node:path";
import type { Config } from "../src/config.js";
import { BindingManager, type BindingManagerOptions } from "../src/binding.js";

function configFor(root: string, profile = "Default"): Config {
  return {
    mo2Root: root,
    permissionCeiling: "metadata-editable",
    allowedProfiles: [profile],
    deny: [],
    snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
    auditRoot: join(root, ".mo2-mcp", "audit"),
  };
}

function moIni(game = "fallout4") {
  return {
    general: { game, gameName: "Fallout 4", gamePath: "C:/Games/Fallout4" },
    settings: { modDirectory: "C:/MO2/mods" },
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function makeDeps(overrides: Partial<BindingManagerOptions> = {}) {
  const sidecars: Array<{
    starts: unknown[];
    stopCalls: number;
    ready: boolean;
    start: (opts: unknown) => Promise<void>;
    stop: () => Promise<void>;
    isReady: () => boolean;
  }> = [];
  const pipes: Array<{
    connectCalls: unknown[];
    closeCalls: number;
    connected: boolean;
    discoverAndConnect: (...args: unknown[]) => Promise<void>;
    close: () => void;
    isConnected: () => boolean;
  }> = [];

  const opts: BindingManagerOptions = {
    loadConfig: async ({ mo2Root }) => configFor(mo2Root),
    readMoIni: async () => moIni(),
    detectMo2Running: async () => ({
      processRunning: true,
      sharedMemoryPresent: false,
      profileLockHeld: false,
      online: true,
      pid: 1234,
      confidence: "high",
    }),
    createSidecarClient: () => {
      const sidecar = {
        starts: [] as unknown[],
        stopCalls: 0,
        ready: false,
        async start(opts: unknown) {
          this.starts.push(opts);
          this.ready = true;
        },
        async stop() {
          this.stopCalls += 1;
          this.ready = false;
        },
        isReady() {
          return this.ready;
        },
      };
      sidecars.push(sidecar);
      return sidecar as never;
    },
    createPipeClient: () => {
      const pipe = {
        connectCalls: [] as unknown[],
        closeCalls: 0,
        connected: false,
        async discoverAndConnect(...args: unknown[]) {
          this.connectCalls.push(args);
          this.connected = true;
        },
        close() {
          this.closeCalls += 1;
          this.connected = false;
        },
        isConnected() {
          return this.connected;
        },
      };
      pipes.push(pipe);
      return pipe as never;
    },
    log: () => {},
    ...overrides,
  };
  return { opts, sidecars, pipes };
}

describe("BindingManager", () => {
  it("starts unbound", () => {
    const manager = new BindingManager(makeDeps().opts);
    expect(manager.getSnapshot()).toEqual({ state: "unbound" });
  });

  it("binds to an MO2 root and exposes a bound context", async () => {
    const { opts } = makeDeps();
    const manager = new BindingManager(opts);

    const snapshot = await manager.bind({ mo2Root: "C:/MO2", profile: "Testing" });

    expect(snapshot).toMatchObject({
      state: "bound",
      mo2Root: "C:/MO2",
      game: "fallout4",
      profile: "Testing",
      pipeConnected: true,
      sidecarReady: true,
    });
    expect(manager.requireBound().mo2Root).toBe("C:/MO2");
    expect(manager.requireBound().config.allowedProfiles[0]).toBe("Testing");
  });

  it("serializes concurrent bind calls without overlapping initialization", async () => {
    let inFlight = 0;
    let maxInFlight = 0;
    const firstLoad = deferred<void>();
    let loads = 0;
    const { opts } = makeDeps({
      loadConfig: async ({ mo2Root }) => {
        inFlight += 1;
        maxInFlight = Math.max(maxInFlight, inFlight);
        loads += 1;
        if (loads === 1) await firstLoad.promise;
        inFlight -= 1;
        return configFor(mo2Root);
      },
    });
    const manager = new BindingManager(opts);

    const first = manager.bind({ mo2Root: "C:/MO2-A" });
    const second = manager.bind({ mo2Root: "C:/MO2-B" });
    firstLoad.resolve();
    await Promise.all([first, second]);

    expect(maxInFlight).toBe(1);
    expect(loads).toBe(2);
    expect(manager.requireBound().mo2Root).toBe("C:/MO2-B");
  });

  it("rebinds the same root by cleaning up the old pipe and sidecar first", async () => {
    const { opts, sidecars, pipes } = makeDeps();
    const manager = new BindingManager(opts);

    await manager.bind({ mo2Root: "C:/MO2" });
    await manager.bind({ mo2Root: "C:/MO2" });

    expect(sidecars).toHaveLength(2);
    expect(pipes).toHaveLength(2);
    expect(sidecars[0].stopCalls).toBe(1);
    expect(pipes[0].closeCalls).toBe(1);
    expect(manager.requireBound().mo2Root).toBe("C:/MO2");
  });

  it("rebinds to a different root", async () => {
    const { opts } = makeDeps();
    const manager = new BindingManager(opts);

    await manager.bind({ mo2Root: "C:/MO2-A" });
    const snapshot = await manager.bind({ mo2Root: "D:/MO2-B" });

    expect(snapshot.mo2Root).toBe("D:/MO2-B");
    expect(manager.requireBound().config.mo2Root).toBe("D:/MO2-B");
  });

  it("unbind is idempotent and cleans up live clients once", async () => {
    const { opts, sidecars, pipes } = makeDeps();
    const manager = new BindingManager(opts);

    await manager.bind({ mo2Root: "C:/MO2" });
    await manager.unbind();
    await manager.unbind();

    expect(manager.getSnapshot()).toEqual({ state: "unbound" });
    expect(sidecars[0].stopCalls).toBe(1);
    expect(pipes[0].closeCalls).toBe(1);
  });

  it("requireBound throws a structured not_bound error when unbound", () => {
    const manager = new BindingManager(makeDeps().opts);

    expect(() => manager.requireBound()).toThrow(/call mo2_session/);
    try {
      manager.requireBound();
    } catch (error) {
      expect((error as { code?: string }).code).toBe("not_bound");
    }
  });

  it("cleans up partial state and records failed snapshot on bind failure", async () => {
    const { opts, sidecars, pipes } = makeDeps({
      detectMo2Running: async () => {
        throw new Error("detection containment breach");
      },
    });
    const manager = new BindingManager(opts);

    await expect(manager.bind({ mo2Root: "C:/MO2" })).resolves.toMatchObject({
      state: "failed",
      error: { code: "bind_failed", message: expect.stringContaining("detection containment breach") },
    });

    expect(sidecars[0].stopCalls).toBe(1);
    expect(pipes).toHaveLength(0);
    expect(() => manager.requireBound()).toThrow(/not bound/);
  });
});
