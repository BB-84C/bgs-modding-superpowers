import { beforeEach, describe, expect, it, vi } from "vitest";
import { EventEmitter } from "node:events";

const spawnCalls: Array<{ command: string; args: string[] }> = [];
let processWaitStatus = "running";

class FakeChild extends EventEmitter {
  stdout = new EventEmitter();
  stderr = new EventEmitter();
}

vi.mock("node:timers/promises", () => ({
  setTimeout: vi.fn(async () => undefined),
}));

vi.mock("../../src/daemon-adapter.js", () => ({
  createPowershellAdapter: vi.fn(() => ({
    call: vi.fn(async () => ({ ok: true, result: { files: ["Dummy.esm"] } })),
  })),
}));

vi.mock("node:child_process", () => ({
  spawn: vi.fn((command: string, args: string[]) => {
    spawnCalls.push({ command, args: [...args] });
    const child = new FakeChild();
    queueMicrotask(() => {
      const mode = args[3] === "process" && args[4] === "launch"
        ? "launch"
        : args[3] === "process" && args[4] === "stop"
          ? "stop"
          : args[3] === "process" && args[4] === "wait"
            ? "wait"
          : "other";

      if (mode === "launch") {
        child.stdout.emit("data", Buffer.from("process launch\nstatus: ok\nxedit-pid: 4242\n"));
      } else if (mode === "stop") {
        child.stdout.emit("data", Buffer.from("process stop\nstatus: stopped\nxedit-pid: 4242\n"));
      } else if (mode === "wait") {
        child.stdout.emit("data", Buffer.from(`process wait\nstatus: ${processWaitStatus}\nxedit-pid: 4242\n`));
      }

      child.emit("close", 0);
    });
    return child;
  }),
}));

describe("launchDaemon readiness-timeout cleanup", () => {
  beforeEach(() => {
    spawnCalls.length = 0;
    processWaitStatus = "running";
    vi.resetModules();
  });

  it("stops the launched pid before surfacing a readiness timeout", async () => {
    const { launchDaemon } = await import("../../src/launch.js");

    await expect(
      launchDaemon({
        clientScript: "D:/awesome-bgs-mod-master/tools/mo2-vfs-launcher/xedit-client.ps1",
        launcherPath: "D:/Starfield MO2/tools/xEdit/SF1Edit64.exe",
        gameMode: "Starfield",
        moProfile: "Default",
        readyTimeoutMs: 0,
      }),
    ).rejects.toThrow(/Daemon not ready within 0 ms \(pid=4242\)/);

    expect(spawnCalls).toHaveLength(2);
    expect(spawnCalls[0]?.args).toContain("launch");
    expect(spawnCalls[1]?.args).toContain("stop");
    expect(spawnCalls[1]?.args).toContain("--xedit-pid");
    expect(spawnCalls[1]?.args).toContain("4242");
  });

  it("forwards iKnowWhatImDoing as --i-know-what-im-doing 1 to xedit-client.ps1 when set", async () => {
    const { launchDaemon } = await import("../../src/launch.js");

    // readyTimeoutMs:0 causes a clean timeout-and-stop after launch, which is
    // fine — we only care about the args of the FIRST spawn (the `launch`
    // invocation). The stop spawn afterwards is exercised by the test above.
    await expect(
      launchDaemon({
        clientScript: "D:/awesome-bgs-mod-master/tools/mo2-vfs-launcher/xedit-client.ps1",
        launcherPath: "D:/awesome-bgs-mod-master/.artifacts/mo2/Stock Game/Fallout 4/Tools/OpenCodeXEdit/xEdit.exe",
        gameMode: "Fallout4",
        moProfile: "Default",
        iKnowWhatImDoing: true,
        readyTimeoutMs: 0,
      }),
    ).rejects.toThrow(/Daemon not ready within 0 ms/);

    const launchSpawn = spawnCalls.find((c) => c.args.includes("launch"));
    expect(launchSpawn).toBeDefined();
    // The consent forwarding pair must appear adjacent: `--i-know-what-im-doing
    // 1`. xedit-client.launch.ps1's ConvertTo-XeditClientOptionMap reads the
    // value (sentinel "1"); any other value silently leaves consent OFF.
    const idx = launchSpawn!.args.indexOf("--i-know-what-im-doing");
    expect(idx).toBeGreaterThanOrEqual(0);
    expect(launchSpawn!.args[idx + 1]).toBe("1");
  });

  it("omits --i-know-what-im-doing entirely when iKnowWhatImDoing is false/undefined", async () => {
    const { launchDaemon } = await import("../../src/launch.js");

    await expect(
      launchDaemon({
        clientScript: "D:/awesome-bgs-mod-master/tools/mo2-vfs-launcher/xedit-client.ps1",
        launcherPath: "D:/awesome-bgs-mod-master/.artifacts/mo2/Stock Game/Fallout 4/Tools/OpenCodeXEdit/xEdit.exe",
        gameMode: "Fallout4",
        moProfile: "Default",
        // iKnowWhatImDoing intentionally omitted
        readyTimeoutMs: 0,
      }),
    ).rejects.toThrow(/Daemon not ready within 0 ms/);

    const launchSpawn = spawnCalls.find((c) => c.args.includes("launch"));
    expect(launchSpawn).toBeDefined();
    expect(launchSpawn!.args).not.toContain("--i-know-what-im-doing");
  });

  it("does not pass --no-starfield-redpill by default", async () => {
    const { launchDaemon } = await import("../../src/launch.js");

    await expect(
      launchDaemon({
        clientScript: "D:/awesome-bgs-mod-master/tools/mo2-vfs-launcher/xedit-client.ps1",
        launcherPath: "D:/Starfield MO2/tools/xEdit/SF1Edit64.exe",
        gameMode: "Starfield",
        moProfile: "Default",
        readyTimeoutMs: 0,
      }),
    ).rejects.toThrow(/Daemon not ready within 0 ms/);

    const launchSpawn = spawnCalls.find((c) => c.args.includes("launch"));
    expect(launchSpawn).toBeDefined();
    expect(launchSpawn!.args).not.toContain("--no-starfield-redpill");
  });

  it("forwards starfieldRedPill false as --no-starfield-redpill 1", async () => {
    const { launchDaemon } = await import("../../src/launch.js");

    await expect(
      launchDaemon({
        clientScript: "D:/awesome-bgs-mod-master/tools/mo2-vfs-launcher/xedit-client.ps1",
        launcherPath: "D:/Starfield MO2/tools/xEdit/SF1Edit64.exe",
        gameMode: "Starfield",
        moProfile: "Default",
        starfieldRedPill: false,
        readyTimeoutMs: 0,
      }),
    ).rejects.toThrow(/Daemon not ready within 0 ms/);

    const launchSpawn = spawnCalls.find((c) => c.args.includes("launch"));
    expect(launchSpawn).toBeDefined();
    const idx = launchSpawn!.args.indexOf("--no-starfield-redpill");
    expect(idx).toBeGreaterThanOrEqual(0);
    expect(launchSpawn!.args[idx + 1]).toBe("1");
  });

  it("waitForExit uses canonical process wait and confirms only exited status", async () => {
    const { launchDaemon } = await import("../../src/launch.js");
    const daemon = await launchDaemon({
      clientScript: "D:/awesome-bgs-mod-master/tools/mo2-vfs-launcher/xedit-client.ps1",
      launcherPath: "D:/Starfield MO2/tools/xEdit/SF1Edit64.exe",
      gameMode: "Starfield",
      moProfile: "Default",
      readyTimeoutMs: 10_000,
    });

    processWaitStatus = "exited";
    await expect(daemon.waitForExit(30_000)).resolves.toBe(true);

    const waitSpawn = spawnCalls.at(-1)!;
    expect(waitSpawn.args).toContain("wait");
    expect(waitSpawn.args).toContain("--timeout-seconds");
    expect(waitSpawn.args).toContain("30");
    expect(spawnCalls.some((call) => call.args.includes("stop"))).toBe(false);
  });

  it.each(["absent", "reused"])("treats process-wait failure plus managed PID %s as confirmed exit", async (status) => {
    const { waitForManagedProcessExit } = await import("../../src/launch.js");
    const run = vi.fn(async (_pwsh: string, args: string[]) => {
      if (args.includes("wait")) throw new Error("xEdit PID is not running");
      return JSON.stringify({ status, executablePath: status === "reused" ? "C:/Windows/notepad.exe" : undefined });
    });

    await expect(waitForManagedProcessExit({
      pwsh: "pwsh",
      clientScript: "client.ps1",
      pid: 4242,
      launcherPath: "D:/tools/xEdit.exe",
      timeoutMs: 30_000,
      run,
    })).resolves.toBe(true);
  });

  it.each([
    ["same managed executable is still alive", async () => JSON.stringify({ status: "same", executablePath: "D:/tools/xEdit.exe" })],
    ["identity probe itself errors", async () => { throw new Error("Get-Process access denied"); }],
  ])("does not confirm exit when process wait fails and %s", async (_label, probeRun) => {
    const { waitForManagedProcessExit } = await import("../../src/launch.js");
    let call = 0;
    const run = vi.fn(async () => {
      call += 1;
      if (call === 1) throw new Error("process wait failed");
      return probeRun();
    });

    await expect(waitForManagedProcessExit({
      pwsh: "pwsh",
      clientScript: "client.ps1",
      pid: 4242,
      launcherPath: "D:/tools/xEdit.exe",
      timeoutMs: 30_000,
      run,
    })).resolves.toBe(false);
  });
});
