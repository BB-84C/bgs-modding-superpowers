import { describe, it, expect } from "vitest";
import { Lifecycle } from "../src/lifecycle.js";

describe("Lifecycle", () => {
  it("starts in not_started state", () => {
    const l = new Lifecycle();
    expect(l.state).toBe("not_started");
    expect(l.context).toEqual({});
  });

  it("transitions not_started → starting → ready", () => {
    const l = new Lifecycle();
    l.markStarting();
    expect(l.state).toBe("starting");
    expect(l.context.startedAt).toBeDefined();

    l.markReady({ sidecarPid: 1234 });
    expect(l.state).toBe("ready");
    expect(l.context.sidecarPid).toBe(1234);
    expect(l.context.readyAt).toBeDefined();
    expect(l.context.startedAt).toBeDefined();
  });

  it("rejects domain tools before ready", () => {
    const l = new Lifecycle();
    const result = l.requireReady();
    expect(result).toEqual({ ok: false, code: "not_ready", state: "not_started" });
  });

  it("requireReady returns ok when state is ready", () => {
    const l = new Lifecycle();
    l.markStarting();
    l.markReady({ sidecarPid: 1 });
    expect(l.requireReady()).toEqual({ ok: true });
  });

  it("markFailed records reason and rejects requireReady", () => {
    const l = new Lifecycle();
    l.markFailed("python sidecar missing");
    expect(l.state).toBe("failed");
    expect(l.context.failureReason).toBe("python sidecar missing");

    const result = l.requireReady();
    expect(result).toEqual({
      ok: false,
      code: "not_ready",
      state: "failed",
      reason: "python sidecar missing",
    });
  });
});
