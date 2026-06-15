import { EventEmitter } from "node:events";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockState = vi.hoisted(() => ({
  connections: [] as string[],
}));

vi.mock("node:fs/promises", () => ({
  readFile: vi.fn(async () => JSON.stringify({ endpoint: "mo2-control-plane-56864" })),
  readdir: vi.fn(async () => ["mo2-control-plane-84640"]),
}));

vi.mock("node:net", () => ({
  connect: vi.fn((path: string) => {
    mockState.connections.push(path);
    const socket = new EventEmitter() as EventEmitter & {
      write: (chunk: string) => boolean;
      destroy: () => void;
    };

    socket.destroy = vi.fn();
    socket.write = vi.fn((chunk: string) => {
      const request = JSON.parse(chunk.trim()) as { request_id?: string; session_id?: string };
      const response = {
        protocol_version: "1",
        request_id: request.request_id,
        session_id: request.session_id,
        ok: true,
        result: { status: "ok" },
        error: null,
      };
      queueMicrotask(() => {
        socket.emit("data", Buffer.from(`${JSON.stringify(response)}\n`, "utf8"));
        socket.emit("close");
      });
      return true;
    });

    queueMicrotask(() => {
      if (path.endsWith("mo2-control-plane-56864")) {
        const error = Object.assign(new Error(`connect ENOENT ${path}`), { code: "ENOENT" });
        socket.emit("error", error);
      } else {
        socket.emit("connect");
        const error = Object.assign(new Error("read EPIPE"), { code: "EPIPE" });
        socket.emit("error", error);
      }
    });

    return socket;
  }),
}));

import { PipeClient } from "../src/pipe-client.js";

describe("PipeClient broker connect", () => {
  beforeEach(() => {
    mockState.connections = [];
  });

  it("falls back to the single live broker pipe when endpoint.json points at a stale pipe", async () => {
    const client = new PipeClient();

    await client.discoverAndConnect("D:/MO2", 1000);

    expect(client.isConnected()).toBe(true);
    expect(mockState.connections).toContain("\\\\.\\pipe\\mo2-control-plane-56864");
    expect(mockState.connections).toContain("\\\\.\\pipe\\mo2-control-plane-84640");
  });
});
