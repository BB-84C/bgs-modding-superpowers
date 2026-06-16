import { EventEmitter } from "node:events";
import { describe, expect, it, vi, beforeEach } from "vitest";

const readFileMock = vi.hoisted(() => vi.fn());
const readdirMock = vi.hoisted(() => vi.fn());
const connectMock = vi.hoisted(() => vi.fn());
const execFileMock = vi.hoisted(() => vi.fn());

vi.mock("node:fs/promises", () => ({
  readFile: readFileMock,
  readdir: readdirMock,
}));

vi.mock("node:net", () => ({
  connect: connectMock,
}));

vi.mock("node:child_process", () => ({
  execFile: execFileMock,
}));

describe("PipeClient MO2 root scoping", () => {
  beforeEach(() => {
    vi.resetModules();
    readFileMock.mockReset();
    readdirMock.mockReset();
    connectMock.mockReset();
    execFileMock.mockReset();
  });

  it("rejects stale endpoint fallback when the only live MO2 process is outside the configured root", async () => {
    readFileMock.mockResolvedValue(JSON.stringify({ endpoint: String.raw`\\.\pipe\mo2_agent_control_999999` }));
    readdirMock.mockResolvedValue(["mo2_agent_control_222222"]);
    execFileMock.mockImplementation((_file: string, _args: string[], maybeCallback: any, maybeCallback2?: any) => {
      const callback = typeof maybeCallback === "function" ? maybeCallback : maybeCallback2;
      callback(null, { stdout: JSON.stringify([{ Id: 222222, Path: String.raw`C:\OtherMO2\ModOrganizer.exe` }]), stderr: "" });
      return {};
    });
    connectMock.mockImplementation((pipePath: string) => {
      const socket = new EventEmitter() as EventEmitter & {
        write: (text: string) => void;
        destroy: () => void;
      };
      socket.write = () => {
        if (pipePath.includes("222222")) {
          socket.emit("data", Buffer.from(`${JSON.stringify({ ok: true, result: { pong: true } })}\n`, "utf8"));
          socket.emit("close");
        }
      };
      socket.destroy = () => undefined;
      queueMicrotask(() => {
        if (pipePath.includes("999999")) {
          const error = new Error("stale pipe") as NodeJS.ErrnoException;
          error.code = "ENOENT";
          socket.emit("error", error);
          socket.emit("close");
        } else {
          socket.emit("connect");
        }
      });
      return socket;
    });

    const { PipeClient } = await import("../src/pipe-client.js");
    const client = new PipeClient();

    await expect(client.discoverAndConnect(String.raw`C:\TargetMO2`, 100)).rejects.toThrow(
      /endpoint_stale_no_matching_mo2_at_root: C:\\TargetMO2/,
    );
  });
});
