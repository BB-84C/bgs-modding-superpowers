import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../src/mo2-process-state.js", () => ({
  probeMo2Process: vi.fn(),
}));
vi.mock("../src/mo2-log.js", () => ({
  tailMo2Log: vi.fn(),
}));

import {
  BrokerEnrichedError,
  _classifyError,
  enrichBrokerError,
} from "../src/broker-error.js";
import { probeMo2Process } from "../src/mo2-process-state.js";
import { tailMo2Log } from "../src/mo2-log.js";

const mockProbe = probeMo2Process as ReturnType<typeof vi.fn>;
const mockTail = tailMo2Log as ReturnType<typeof vi.fn>;

describe("BrokerEnrichedError", () => {
  it("is an Error subclass and preserves code/details/message", () => {
    const err = new BrokerEnrichedError({
      code: "mo2_gui_unresponsive",
      message: "MO2 frozen",
      details: { method: "mods.set_active", processState: { alive: true, responding: false } },
    });
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(BrokerEnrichedError);
    expect(err.name).toBe("BrokerEnrichedError");
    expect(err.code).toBe("mo2_gui_unresponsive");
    expect(err.message).toBe("MO2 frozen");
    expect(err.details).toEqual({
      method: "mods.set_active",
      processState: { alive: true, responding: false },
    });
  });

  it("carries an empty details object when nothing is provided beyond required fields", () => {
    const err = new BrokerEnrichedError({ code: "broker_error", message: "boom", details: {} });
    expect(err.code).toBe("broker_error");
    expect(err.details).toEqual({});
  });
});

describe("_classifyError", () => {
  it("returns mo2_gui_unresponsive when MO2 is alive but not responding", () => {
    const result = _classifyError("pipe call timeout (mods.set_active)", {
      alive: true,
      pid: 1234,
      responding: false,
    });
    expect(result.code).toBe("mo2_gui_unresponsive");
    expect(result.hint).toContain("modal dialog");
    expect(result.message).toContain("not responding");
  });

  it("returns pipe_call_timeout when MO2 is responding and message matches timeout", () => {
    const result = _classifyError("pipe call timeout (mods.create)", {
      alive: true,
      pid: 1234,
      responding: true,
    });
    expect(result.code).toBe("pipe_call_timeout");
    expect(result.message).toBe("pipe call timeout (mods.create)");
    expect(result.hint).toBeUndefined();
  });

  it("returns pipe_call_timeout when MO2 process is gone (alive=false)", () => {
    const result = _classifyError("pipe call timeout (mods.set_active)", { alive: false });
    expect(result.code).toBe("pipe_call_timeout");
  });

  it("returns pipe_empty_response for empty-response failures", () => {
    const result = _classifyError("empty pipe response (system.ping)", { alive: true, responding: true });
    expect(result.code).toBe("pipe_empty_response");
  });

  it("returns pipe_parse_error for parse failures", () => {
    const result = _classifyError("pipe response parse error: Unexpected token", {
      alive: true,
      responding: true,
    });
    expect(result.code).toBe("pipe_parse_error");
  });

  it("returns broker_error for unrecognized messages", () => {
    const result = _classifyError("connect ECONNREFUSED", { alive: true, responding: true });
    expect(result.code).toBe("broker_error");
    expect(result.message).toBe("connect ECONNREFUSED");
  });

  it("prioritizes mo2_gui_unresponsive over message-prefix matching", () => {
    // Even with a timeout-shaped message, alive+responding=false wins.
    const result = _classifyError("empty pipe response (mods.set_active)", {
      alive: true,
      pid: 99,
      responding: false,
    });
    expect(result.code).toBe("mo2_gui_unresponsive");
  });

  it("does not return mo2_gui_unresponsive when responding is undefined", () => {
    const result = _classifyError("pipe call timeout", { alive: true, pid: 99 });
    expect(result.code).toBe("pipe_call_timeout");
  });
});

describe("enrichBrokerError", () => {
  beforeEach(() => {
    mockProbe.mockReset();
    mockTail.mockReset();
  });

  it("builds details with processState and log tail when both available", async () => {
    mockProbe.mockResolvedValue({ alive: true, pid: 1234, responding: false });
    mockTail.mockResolvedValue({
      lines: ["[2026-06-17 03:00:00.123 E] Cannot launch program"],
      truncated: false,
      logPath: "D:\\mo2\\logs\\mo2.log",
    });

    const err = await enrichBrokerError(
      new Error("pipe call timeout (mods.set_active)"),
      "mods.set_active",
      "D:\\mo2",
      Date.now() - 5000,
    );

    expect(err).toBeInstanceOf(BrokerEnrichedError);
    expect(err.code).toBe("mo2_gui_unresponsive");
    expect(err.details.method).toBe("mods.set_active");
    expect(err.details.originalMessage).toBe("pipe call timeout (mods.set_active)");
    expect(err.details.processState).toEqual({ alive: true, pid: 1234, responding: false });
    expect(err.details.mo2_log_tail).toEqual({
      lines: ["[2026-06-17 03:00:00.123 E] Cannot launch program"],
      truncated: false,
      logPath: "D:\\mo2\\logs\\mo2.log",
    });
    expect(err.details.hint).toContain("modal dialog");
  });

  it("omits mo2_log_tail from details when log read returned no lines", async () => {
    mockProbe.mockResolvedValue({ alive: true, pid: 1234, responding: true });
    mockTail.mockResolvedValue({ lines: [], truncated: false, logPath: "D:\\mo2\\logs\\mo2.log" });

    const err = await enrichBrokerError(
      new Error("pipe call timeout (mods.create)"),
      "mods.create",
      "D:\\mo2",
      Date.now(),
    );

    expect(err.code).toBe("pipe_call_timeout");
    expect(err.details).not.toHaveProperty("mo2_log_tail");
    expect(err.details).not.toHaveProperty("hint");
  });

  it("falls back gracefully when probe rejects", async () => {
    mockProbe.mockRejectedValue(new Error("powershell missing"));
    mockTail.mockResolvedValue({ lines: [], truncated: false, logPath: "" });

    const err = await enrichBrokerError(
      new Error("pipe call timeout (mods.create)"),
      "mods.create",
      "D:\\mo2",
      Date.now(),
    );

    expect(err.code).toBe("pipe_call_timeout");
    expect(err.details.processState).toEqual({ alive: false });
  });

  it("falls back gracefully when tail rejects", async () => {
    mockProbe.mockResolvedValue({ alive: false });
    mockTail.mockRejectedValue(new Error("read failed"));

    const err = await enrichBrokerError(
      "raw string error",
      "system.ping",
      "D:\\mo2",
      Date.now(),
    );

    expect(err.code).toBe("broker_error");
    expect(err.details.originalMessage).toBe("raw string error");
    expect(err.details).not.toHaveProperty("mo2_log_tail");
  });

  it("preserves the method name in details for downstream audit/diagnostics", async () => {
    mockProbe.mockResolvedValue({ alive: true, pid: 1, responding: true });
    mockTail.mockResolvedValue({ lines: [], truncated: false, logPath: "" });

    const err = await enrichBrokerError(
      new Error("empty pipe response (mods.meta_write)"),
      "mods.meta_write",
      "D:\\mo2",
      Date.now(),
    );

    expect(err.details.method).toBe("mods.meta_write");
    expect(err.code).toBe("pipe_empty_response");
  });
});
