/**
 * Integration tests for pipe-client's call() wrapper: verify that raw failures
 * coming out of _rawCall are wrapped into BrokerEnrichedError instances with
 * the L1 process state + L2 log tail attached.
 *
 * Strategy: mock node:net so the socket fires error/close paths deterministically,
 * mock probeMo2Process / tailMo2Log to drive classification, then invoke
 * `client.call()` and assert the resulting error shape.
 */
import { EventEmitter } from "node:events";
import { beforeEach, describe, expect, it, vi } from "vitest";

const netState = vi.hoisted(() => ({
  mode: "timeout" as
    | "timeout"
    | "empty"
    | "parse-error"
    | "socket-error"
    | "discovery-success",
  parseErrorBody: "not-json\n",
}));

vi.mock("node:net", () => ({
  connect: vi.fn((_path: string) => {
    const socket = new EventEmitter() as EventEmitter & {
      write: (chunk: string) => boolean;
      destroy: () => void;
    };
    socket.destroy = vi.fn();
    socket.write = vi.fn(() => true);

    const mode = netState.mode;
    queueMicrotask(() => {
      if (mode === "discovery-success") {
        // Emit a valid ping response then close.
        socket.emit("connect");
        const response = JSON.stringify({
          protocol_version: "1",
          request_id: "x",
          session_id: "mo2-mcp",
          ok: true,
          result: {},
          error: null,
        });
        socket.emit("data", Buffer.from(`${response}\n`, "utf8"));
        socket.emit("close");
        return;
      }
      socket.emit("connect");
      if (mode === "timeout") {
        // Never resolve — the call's timeout will fire and destroy().
        return;
      }
      if (mode === "empty") {
        socket.emit("close");
        return;
      }
      if (mode === "parse-error") {
        socket.emit("data", Buffer.from(netState.parseErrorBody, "utf8"));
        socket.emit("close");
        return;
      }
      if (mode === "socket-error") {
        const err = Object.assign(new Error("ECONNREFUSED"), { code: "ECONNREFUSED" });
        socket.emit("error", err);
        return;
      }
    });

    return socket;
  }),
}));

vi.mock("../src/mo2-process-state.js", () => ({
  probeMo2Process: vi.fn(),
}));
vi.mock("../src/mo2-log.js", () => ({
  tailMo2Log: vi.fn(),
}));

import { PipeClient } from "../src/pipe-client.js";
import { BrokerEnrichedError } from "../src/broker-error.js";
import { probeMo2Process } from "../src/mo2-process-state.js";
import { tailMo2Log } from "../src/mo2-log.js";

const mockProbe = probeMo2Process as ReturnType<typeof vi.fn>;
const mockTail = tailMo2Log as ReturnType<typeof vi.fn>;

/**
 * Build a PipeClient that has been "primed" as if discoverAndConnect
 * succeeded: pipeName + mo2Root are set, so call() enters the enrichment
 * path on failure.
 */
function primedClient(): PipeClient {
  const client = new PipeClient();
  // Use Object.assign on a typed cast to set the private fields without
  // mutating the class shape.
  Object.assign(client as unknown as Record<string, unknown>, {
    pipeName: "mo2-control-plane-test",
    mo2Root: "D:\\mo2-test",
  });
  return client;
}

describe("PipeClient.call enrichment", () => {
  beforeEach(() => {
    mockProbe.mockReset();
    mockTail.mockReset();
    netState.mode = "timeout";
    netState.parseErrorBody = "not-json\n";
  });

  it("rejects synchronously with the existing message when pipe is not discovered (no enrichment)", async () => {
    const client = new PipeClient();
    await expect(client.call("system.ping", {})).rejects.toThrow(/not discovered/);
    expect(mockProbe).not.toHaveBeenCalled();
    expect(mockTail).not.toHaveBeenCalled();
  });

  it("wraps a timeout as mo2_gui_unresponsive when MO2 is alive but not responding", async () => {
    netState.mode = "timeout";
    mockProbe.mockResolvedValue({ alive: true, pid: 4321, responding: false });
    mockTail.mockResolvedValue({
      lines: ["[2026-06-17 03:00:00.000 E] Cannot launch program"],
      truncated: false,
      logPath: "D:\\mo2-test\\logs\\mo2.log",
    });

    const client = primedClient();
    const promise = client.call("mods.set_active", { name: "X" }, 30);
    await expect(promise).rejects.toBeInstanceOf(BrokerEnrichedError);
    const err = await promise.catch((e: BrokerEnrichedError) => e);
    expect(err.code).toBe("mo2_gui_unresponsive");
    expect(err.message).toContain("not responding");
    expect(err.details.method).toBe("mods.set_active");
    expect(err.details.processState).toEqual({ alive: true, pid: 4321, responding: false });
    expect(err.details.originalMessage).toContain("pipe call timeout");
    expect(err.details.mo2_log_tail).toBeDefined();
    expect(err.details.hint).toContain("modal dialog");
  });

  it("wraps a timeout as pipe_call_timeout when MO2 is alive and responding", async () => {
    netState.mode = "timeout";
    mockProbe.mockResolvedValue({ alive: true, pid: 1234, responding: true });
    mockTail.mockResolvedValue({ lines: [], truncated: false, logPath: "" });

    const client = primedClient();
    const promise = client.call("mods.create", { name: "X" }, 30);
    const err = await promise.catch((e: BrokerEnrichedError) => e);
    expect(err).toBeInstanceOf(BrokerEnrichedError);
    expect(err.code).toBe("pipe_call_timeout");
    expect(err.details.processState).toEqual({ alive: true, pid: 1234, responding: true });
    expect(err.details.hint).toBeUndefined();
    expect(err.details.mo2_log_tail).toBeUndefined();
  });

  it("wraps a timeout as pipe_call_timeout when the MO2 process is gone", async () => {
    netState.mode = "timeout";
    mockProbe.mockResolvedValue({ alive: false });
    mockTail.mockResolvedValue({ lines: [], truncated: false, logPath: "" });

    const client = primedClient();
    const promise = client.call("mods.create", {}, 30);
    const err = await promise.catch((e: BrokerEnrichedError) => e);
    expect(err.code).toBe("pipe_call_timeout");
    expect(err.details.processState).toEqual({ alive: false });
  });

  it("wraps an empty-pipe-response failure as pipe_empty_response", async () => {
    netState.mode = "empty";
    mockProbe.mockResolvedValue({ alive: true, pid: 1, responding: true });
    mockTail.mockResolvedValue({ lines: [], truncated: false, logPath: "" });

    const client = primedClient();
    const err = await client
      .call("system.ping", {})
      .catch((e: BrokerEnrichedError) => e);
    expect(err.code).toBe("pipe_empty_response");
    expect(err.details.originalMessage).toContain("empty pipe response");
  });

  it("wraps a parse-error failure as pipe_parse_error", async () => {
    netState.mode = "parse-error";
    mockProbe.mockResolvedValue({ alive: true, pid: 1, responding: true });
    mockTail.mockResolvedValue({ lines: [], truncated: false, logPath: "" });

    const client = primedClient();
    const err = await client
      .call("mods.list", {})
      .catch((e: BrokerEnrichedError) => e);
    expect(err.code).toBe("pipe_parse_error");
    expect(err.details.originalMessage).toContain("parse error");
  });

  it("wraps a socket-error failure as broker_error", async () => {
    netState.mode = "socket-error";
    mockProbe.mockResolvedValue({ alive: false });
    mockTail.mockResolvedValue({ lines: [], truncated: false, logPath: "" });

    const client = primedClient();
    const err = await client
      .call("mods.list", {})
      .catch((e: BrokerEnrichedError) => e);
    expect(err.code).toBe("broker_error");
    expect(err.details.originalMessage).toContain("ECONNREFUSED");
  });

  it("attaches mo2_log_tail to details when the log has recent lines", async () => {
    netState.mode = "timeout";
    mockProbe.mockResolvedValue({ alive: true, pid: 1, responding: true });
    mockTail.mockResolvedValue({
      lines: ["[2026-06-17 03:00:00.000 E] something broke"],
      truncated: false,
      logPath: "D:\\mo2-test\\logs\\mo2.log",
    });

    const client = primedClient();
    const err = await client.call("mods.create", {}, 30).catch((e: BrokerEnrichedError) => e);
    expect(err.details.mo2_log_tail).toEqual({
      lines: ["[2026-06-17 03:00:00.000 E] something broke"],
      truncated: false,
      logPath: "D:\\mo2-test\\logs\\mo2.log",
    });
  });

  it("omits mo2_log_tail from details when log read returned no lines", async () => {
    netState.mode = "timeout";
    mockProbe.mockResolvedValue({ alive: true, pid: 1, responding: true });
    mockTail.mockResolvedValue({ lines: [], truncated: false, logPath: "" });

    const client = primedClient();
    const err = await client.call("mods.create", {}, 30).catch((e: BrokerEnrichedError) => e);
    expect(err.details.mo2_log_tail).toBeUndefined();
  });

  it("includes a modal-dialog hint only on mo2_gui_unresponsive", async () => {
    // Responding => no hint.
    netState.mode = "timeout";
    mockProbe.mockResolvedValue({ alive: true, pid: 1, responding: true });
    mockTail.mockResolvedValue({ lines: [], truncated: false, logPath: "" });
    const client = primedClient();
    let err = await client.call("mods.create", {}, 30).catch((e: BrokerEnrichedError) => e);
    expect(err.details.hint).toBeUndefined();

    // Now flip to non-responding.
    mockProbe.mockResolvedValue({ alive: true, pid: 1, responding: false });
    err = await client.call("mods.create", {}, 30).catch((e: BrokerEnrichedError) => e);
    expect(err.details.hint).toContain("modal dialog");
  });

  it("survives probe / tail rejection without leaking the underlying error", async () => {
    netState.mode = "timeout";
    mockProbe.mockRejectedValue(new Error("powershell missing"));
    mockTail.mockRejectedValue(new Error("read failed"));

    const client = primedClient();
    const err = await client.call("mods.create", {}, 30).catch((e: BrokerEnrichedError) => e);
    expect(err).toBeInstanceOf(BrokerEnrichedError);
    expect(err.code).toBe("pipe_call_timeout");
    expect(err.details.processState).toEqual({ alive: false });
    expect(err.details.mo2_log_tail).toBeUndefined();
  });
});
