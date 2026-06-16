import { afterEach, describe, expect, it, vi } from "vitest";

const execFileMock = vi.hoisted(() => vi.fn());

vi.mock("node:child_process", () => ({
  execFile: execFileMock,
}));

describe("detectMo2Running root scoping", () => {
  afterEach(() => {
    vi.resetModules();
    execFileMock.mockReset();
  });

  it("ignores ModOrganizer processes whose executable path is outside mo2Root", async () => {
    execFileMock.mockImplementation((file: string, _args: string[], maybeCallback: any, maybeCallback2?: any) => {
      const callback = typeof maybeCallback === "function" ? maybeCallback : maybeCallback2;
      if (file === "tasklist") {
        callback(null, { stdout: '"ModOrganizer.exe","1234","Console","1","100 K"', stderr: "" });
        return {};
      }
      callback(null, { stdout: JSON.stringify([{ Id: 1234, Path: String.raw`C:\OtherMO2\ModOrganizer.exe` }]), stderr: "" });
      return {};
    });
    const { detectMo2Running } = await import("../src/detection.js");

    const result = await detectMo2Running({ mo2Root: String.raw`C:\TargetMO2` });

    expect(result.processRunning).toBe(false);
    expect(result.pid).toBeNull();
    expect(result.sharedMemoryPresent).toBe("unknown");
    expect(result.profileLockHeld).toBe(false);
    expect(result.confidence).toBe("low");
  });

  it("reports profileLockHeld when the configured profile modlist has an exclusive lock", async () => {
    execFileMock.mockImplementation((file: string, args: string[], maybeCallback: any, maybeCallback2?: any) => {
      const callback = typeof maybeCallback === "function" ? maybeCallback : maybeCallback2;
      const command = args.join("\n");
      if (file === "tasklist") {
        callback(null, { stdout: '"ModOrganizer.exe","1234","Console","1","100 K"', stderr: "" });
        return {};
      }
      if (command.includes("modlist.txt")) {
        callback(null, { stdout: "locked\n", stderr: "" });
        return {};
      }
      callback(null, { stdout: JSON.stringify([{ Id: 1234, Path: String.raw`C:\TargetMO2\ModOrganizer.exe` }]), stderr: "" });
      return {};
    });
    const { detectMo2Running } = await import("../src/detection.js");

    const result = await detectMo2Running({
      mo2Root: String.raw`C:\TargetMO2`,
      profileDir: String.raw`C:\TargetMO2\profiles\Default`,
    });

    expect(result.processRunning).toBe(true);
    expect(result.pid).toBe(1234);
    expect(result.sharedMemoryPresent).toBe("unknown");
    expect(result.profileLockHeld).toBe(true);
    expect(result.confidence).toBe("medium");
  });
});
