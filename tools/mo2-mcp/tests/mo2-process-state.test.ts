import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("node:child_process", () => ({
  execFile: vi.fn(),
}));

import { execFile } from "node:child_process";
import { probeMo2Process } from "../src/mo2-process-state.js";

const mockExecFile = execFile as unknown as ReturnType<typeof vi.fn>;

type ExecFileCallback = (
  err: Error | null,
  result: { stdout: string; stderr: string } | undefined,
) => void;

function setStdout(stdout: string): void {
  mockExecFile.mockImplementation(
    (_file: string, _args: string[], maybeCb: ExecFileCallback | unknown, maybeCb2?: ExecFileCallback) => {
      const cb = (typeof maybeCb === "function" ? maybeCb : maybeCb2) as ExecFileCallback;
      cb(null, { stdout, stderr: "" });
      return {};
    },
  );
}

function setError(err: Error): void {
  mockExecFile.mockImplementation(
    (_file: string, _args: string[], maybeCb: ExecFileCallback | unknown, maybeCb2?: ExecFileCallback) => {
      const cb = (typeof maybeCb === "function" ? maybeCb : maybeCb2) as ExecFileCallback;
      cb(err, undefined);
      return {};
    },
  );
}

describe("probeMo2Process", () => {
  beforeEach(() => {
    mockExecFile.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns alive + responding=true + pid + startTime on healthy MO2", async () => {
    setStdout('{"Id":1234,"Responding":true,"StartTime":"2026-06-17T03:00:00.0000000+00:00"}');
    const result = await probeMo2Process("D:\\mo2");
    expect(result).toEqual({
      alive: true,
      pid: 1234,
      responding: true,
      startTime: "2026-06-17T03:00:00.0000000+00:00",
    });
  });

  it("returns alive + responding=false when MO2 main thread is frozen", async () => {
    setStdout('{"Id":4321,"Responding":false,"StartTime":"2026-06-17T02:00:00.0000000+00:00"}');
    const result = await probeMo2Process("D:\\mo2");
    expect(result).toEqual({
      alive: true,
      pid: 4321,
      responding: false,
      startTime: "2026-06-17T02:00:00.0000000+00:00",
    });
  });

  it("returns alive:false on empty stdout (no matching process)", async () => {
    setStdout("");
    const result = await probeMo2Process("D:\\mo2");
    expect(result).toEqual({ alive: false });
  });

  it("returns alive:false on whitespace-only stdout", async () => {
    setStdout("   \r\n");
    const result = await probeMo2Process("D:\\mo2");
    expect(result).toEqual({ alive: false });
  });

  it("returns alive:false when execFile throws (powershell missing, etc.)", async () => {
    setError(Object.assign(new Error("not found"), { code: "ENOENT" }));
    const result = await probeMo2Process("D:\\mo2");
    expect(result).toEqual({ alive: false });
  });

  it("returns alive:false when stdout is malformed JSON", async () => {
    setStdout("not-json");
    const result = await probeMo2Process("D:\\mo2");
    expect(result).toEqual({ alive: false });
  });

  it("picks the first entry when PowerShell returns an array of multiple matching processes", async () => {
    setStdout(
      '[{"Id":111,"Responding":true,"StartTime":"2026-06-17T01:00:00.0000000+00:00"},' +
        '{"Id":222,"Responding":false,"StartTime":"2026-06-17T02:00:00.0000000+00:00"}]',
    );
    const result = await probeMo2Process("D:\\mo2");
    expect(result).toEqual({
      alive: true,
      pid: 111,
      responding: true,
      startTime: "2026-06-17T01:00:00.0000000+00:00",
    });
  });

  it("handles missing Responding/StartTime fields gracefully", async () => {
    setStdout('{"Id":5555}');
    const result = await probeMo2Process("D:\\mo2");
    expect(result.alive).toBe(true);
    expect(result.pid).toBe(5555);
    expect(result.responding).toBeUndefined();
    expect(result.startTime).toBeUndefined();
  });

  it("returns alive:false when Id field is missing", async () => {
    setStdout('{"Responding":true}');
    const result = await probeMo2Process("D:\\mo2");
    expect(result).toEqual({ alive: false });
  });

  it("invokes pwsh with the mo2Root embedded in the Where-Object filter", async () => {
    setStdout("");
    await probeMo2Process("B:\\WastelandBlues 2.0");
    expect(mockExecFile).toHaveBeenCalledTimes(1);
    const args = mockExecFile.mock.calls[0];
    expect(args[0]).toBe("pwsh");
    const psScript = (args[1] as string[])[2];
    expect(psScript).toContain("B:\\WastelandBlues 2.0");
    expect(psScript).toContain("ModOrganizer*");
  });
});
