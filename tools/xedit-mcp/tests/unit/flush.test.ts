import { describe, expect, it, vi } from "vitest";

import type { AuditRecord } from "../../src/audit.js";
import type { DaemonAdapter, NativeEnvelope } from "../../src/daemon-adapter.js";
import { makeFlushHandler, retryFailedFlushExit, type FlushSummary } from "../../src/flush.js";
import { PendingSaveTracker } from "../../src/pending-save.js";

function adapterFor(flush: NativeEnvelope | Error, supports: unknown = { sessionFlush: true }): DaemonAdapter {
  return {
    async call(call) {
      if (call.command === "system.capabilities") {
        return { ok: true, command: call.command, result: { supports } };
      }
      if (call.command === "session.flush") {
        if (flush instanceof Error) throw flush;
        return flush;
      }
      throw new Error(`unexpected ${call.command}`);
    },
  };
}

function harness(flush: NativeEnvelope | Error, options: { exited?: boolean; supports?: unknown } = {}) {
  const tracker = new PendingSaveTracker();
  tracker.observeSuccessfulSave({ savePendingShutdownCount: 1 });
  const audits: AuditRecord[] = [];
  const onConfirmedExit = vi.fn();
  const onExitFailure = vi.fn();
  const waitForExit = vi.fn(async () => options.exited ?? true);
  const handler = makeFlushHandler({
    adapter: adapterFor(flush, options.supports ?? { sessionFlush: true }),
    tracker,
    waitForExit,
    onConfirmedExit,
    onExitFailure,
    getContext: () => ({ sessionId: "s", daemonPid: 42 }),
    audit: { async append(record) { audits.push(record); } },
    exitTimeoutMs: 30_000,
  });
  return { handler, tracker, audits, onConfirmedExit, onExitFailure, waitForExit };
}

describe("xedit_flush lifecycle owner", () => {
  it("waits for confirmed exit, clears blocking tracker, and completes", async () => {
    const h = harness({
      ok: true,
      command: "session.flush",
      result: {
        flushedFiles: [{ fileName: "Patch.esp", renamed: true }],
        pendingRemaining: [],
        pendingRemainingCount: 0,
        dirtyState: { pendingShutdownFiles: [{ file: { name: "Patch.esp" } }], pendingShutdownCount: 1 },
      },
    });

    const env = await h.handler({ force: true });

    expect(env).toMatchObject({ ok: true, status: "completed" });
    expect(h.waitForExit).toHaveBeenCalledWith(30_000);
    expect(h.onConfirmedExit).toHaveBeenCalledTimes(1);
    expect(h.onExitFailure).not.toHaveBeenCalled();
    expect(h.tracker.snapshot()).toEqual({ count: 0, files: [] });
    expect(h.audits[0]).toMatchObject({
      tool: "xedit_flush",
      force: true,
      daemonExited: true,
      flushed: { attempted: 1, renamed: 1, failed: 0 },
      pendingRemaining: 0,
    });
  });

  it("returns partial with HIGH warning and a nonblocking residue after confirmed exit", async () => {
    const h = harness({
      ok: true,
      command: "session.flush",
      result: {
        flushedFiles: [{ fileName: "Patch.esp", renamed: false, error: "locked" }],
        pendingRemaining: ["Patch.esp"],
        pendingRemainingCount: 1,
        dirtyState: { pendingShutdownFiles: [], pendingShutdownCount: 0 },
      },
    });

    const env = await h.handler({});

    expect(env).toMatchObject({
      ok: true,
      status: "partial",
      warnings: [{
        code: "FLUSH_INCOMPLETE",
        severity: "HIGH",
        message: expect.stringContaining("retry"),
      }],
      data: {
        nextStep: expect.stringContaining("fresh daemon"),
      },
    });
    expect(h.onConfirmedExit).toHaveBeenCalledWith(expect.objectContaining({
      status: "partial",
      pendingRemaining: ["Patch.esp"],
    }));
    expect(h.tracker.snapshot()).toEqual({ count: 0, files: [] });
  });

  it.each(["consent_required", "state_conflict"])("keeps ready semantics for %s", async (code) => {
    const h = harness({
      ok: false,
      command: "session.flush",
      error: { code, message: code },
    });
    const env = await h.handler({});
    expect(env).toMatchObject({ ok: false, code });
    expect(h.waitForExit).not.toHaveBeenCalled();
    expect(h.onConfirmedExit).not.toHaveBeenCalled();
    expect(h.onExitFailure).not.toHaveBeenCalled();
    expect(h.tracker.snapshot().count).toBe(1);
  });

  it("refuses unsupported daemon without disturbing ready state", async () => {
    const h = harness({ ok: true, command: "session.flush", result: {} }, { supports: {} });
    const env = await h.handler({});
    expect(env).toMatchObject({ ok: false, code: "unsupported_by_daemon" });
    expect(h.waitForExit).not.toHaveBeenCalled();
    expect(h.onExitFailure).not.toHaveBeenCalled();
  });

  it("fails closed on transport exception with unconfirmed exit and preserves prior tracker", async () => {
    const h = harness(new Error("pipe closed"), { exited: false });
    const env = await h.handler({});
    expect(env.ok).toBe(false);
    expect(h.onExitFailure).toHaveBeenCalledTimes(1);
    expect(h.onConfirmedExit).not.toHaveBeenCalled();
    expect(h.tracker.snapshot().count).toBe(1);
  });

  it.each([
    [[], 0],
    [["StillPending.esp"], 1],
  ])("fails retained on known result with unconfirmed exit and adopts post-drain pending state %#", async (remaining, count) => {
    const h = harness({
      ok: true,
      command: "session.flush",
      result: {
        flushedFiles: [{ fileName: "Patch.esp", renamed: remaining.length === 0 }],
        pendingRemaining: remaining,
        pendingRemainingCount: count,
      },
    }, { exited: false });

    const env = await h.handler({});

    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.detail).toMatchObject({
      flushed: { attempted: 1, renamed: remaining.length === 0 ? 1 : 0, failed: remaining.length === 0 ? 0 : 1 },
      pendingRemaining: remaining,
      pendingRemainingCount: count,
    });
    expect(h.tracker.snapshot()).toEqual({ count, files: remaining });
    expect(h.onExitFailure).toHaveBeenCalledWith(
      expect.stringContaining("did not confirm exit"),
      expect.objectContaining({
        outcome: "known",
        daemonExited: false,
        daemonPid: 42,
        pendingRemainingCount: count,
      }),
    );
    expect(h.audits[0]).toMatchObject({
      risk: "flush_exit_unconfirmed",
      pendingShutdownSave: { count, files: remaining },
      pendingRemaining: count,
      daemonExited: false,
      flushOutcome: "known",
    });
  });

  it("confirms exit and clears blocking state after a post-drain daemon error", async () => {
    const h = harness({
      ok: false,
      command: "session.flush",
      error: { code: "internal_error", message: "response construction failed after drain" },
    });

    const env = await h.handler({});

    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.detail).toMatchObject({ nativeCode: "internal_error" });
    expect(h.waitForExit).toHaveBeenCalled();
    expect(h.onConfirmedExit).toHaveBeenCalledWith(expect.objectContaining({
      status: "partial",
      outcome: "unknown",
      daemonExited: true,
      daemonPid: 42,
      at: expect.any(String),
      pendingRemainingCount: 1,
    }));
    expect(h.tracker.snapshot()).toEqual({ count: 0, files: [] });
    expect(h.audits[0]).toMatchObject({
      daemonExited: true,
      pendingRemaining: 1,
      risk: "flush_outcome_unknown",
    });
  });

  it("keeps a responding daemon ready when structured internal_error did not arm exit", async () => {
    const h = harness({
      ok: false,
      command: "session.flush",
      error: { code: "internal_error", message: "pre-drain validation failed" },
    }, { exited: false });

    const env = await h.handler({});

    expect(env).toMatchObject({ ok: false, code: "daemon_error" });
    if (env.ok) throw new Error("expected refusal");
    expect(env.detail).toMatchObject({ nativeCode: "internal_error" });
    expect(h.waitForExit).toHaveBeenCalled();
    expect(h.onConfirmedExit).not.toHaveBeenCalled();
    expect(h.onExitFailure).not.toHaveBeenCalled();
    expect(h.tracker.snapshot().count).toBe(1);
    expect(h.audits[0]).toMatchObject({ daemonExited: false, pendingShutdownSave: { count: 1 } });
  });

  it("preserves prior anonymous pending count in transport-unknown sticky residue", async () => {
    const h = harness(new Error("pipe closed"));
    const env = await h.handler({});

    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.summary).toContain("outcome unknown");
    expect(env.hint).toContain("process exit confirmed");
    expect(h.onConfirmedExit).toHaveBeenCalledWith(expect.objectContaining({
      outcome: "unknown",
      pendingRemaining: [],
      pendingRemainingCount: 1,
    }));
    expect(h.tracker.snapshot()).toEqual({ count: 0, files: [] });
  });

  it("carries known pending file names into transport-unknown residue", async () => {
    const tracker = new PendingSaveTracker();
    tracker.observeDirtyState({
      pendingShutdownFiles: [{ tempFile: "Patch.save", file: { name: "Patch.esp", fileName: "Patch.esp" } }],
      pendingShutdownCount: 1,
    });
    const onConfirmedExit = vi.fn();
    const handler = makeFlushHandler({
      adapter: adapterFor(new Error("pipe closed")),
      tracker,
      waitForExit: async () => true,
      onConfirmedExit,
      onExitFailure: () => {},
      getContext: () => ({ sessionId: "s" }),
      audit: { async append() {} },
    });

    await handler({});

    expect(onConfirmedExit).toHaveBeenCalledWith(expect.objectContaining({
      pendingRemaining: ["Patch.esp"],
      pendingRemainingCount: 1,
    }));
  });

  it("does not feed the pre-drain dirtyState back into the tracker", async () => {
    const h = harness({
      ok: true,
      command: "session.flush",
      result: {
        flushedFiles: [],
        pendingRemaining: [],
        pendingRemainingCount: 0,
        dirtyState: { pendingShutdownFiles: [{ file: { name: "Stale.esp" } }], pendingShutdownCount: 99 },
      },
    });
    await h.handler({});
    expect(h.tracker.snapshot()).toEqual({ count: 0, files: [] });
  });

  it("forwards force without inventing it when omitted", async () => {
    const calls: Array<{ command: string; args?: Record<string, unknown> }> = [];
    const tracker = new PendingSaveTracker();
    const handler = makeFlushHandler({
      adapter: {
        async call(call) {
          calls.push(call);
          if (call.command === "system.capabilities") {
            return { ok: true, command: call.command, result: { supports: { sessionFlush: true } } };
          }
          return {
            ok: true,
            command: call.command,
            result: { flushedFiles: [], pendingRemaining: [], pendingRemainingCount: 0 },
          };
        },
      },
      tracker,
      waitForExit: async () => true,
      onConfirmedExit: () => {},
      onExitFailure: () => {},
      getContext: () => ({ sessionId: "s" }),
      audit: { async append() {} },
    });

    await handler({});
    await handler({ force: true });

    const flushCalls = calls.filter((call) => call.command === "session.flush");
    expect(flushCalls[0]?.args).toEqual({});
    expect(flushCalls[1]?.args).toEqual({ force: true });
  });

  it.each([
    ["missing fields", {}],
    ["count/list mismatch", {
      flushedFiles: [],
      pendingRemaining: ["Patch.esp"],
      pendingRemainingCount: 0,
    }],
    ["flushed item without renamed", {
      flushedFiles: [{ fileName: "Patch.esp" }],
      pendingRemaining: [],
      pendingRemainingCount: 0,
    }],
  ])("treats malformed successful flush result as unknown: %s", async (_label, result) => {
    const h = harness({ ok: true, command: "session.flush", result });

    const env = await h.handler({});

    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected malformed refusal");
    expect(env.summary).toContain("flush result malformed");
    expect(env.summary).toContain("outcome unknown");
    expect(h.onConfirmedExit).toHaveBeenCalledWith(expect.objectContaining({
      status: "partial",
      outcome: "unknown",
      pendingRemainingCount: 1,
    }));
    expect(h.tracker.snapshot()).toEqual({ count: 0, files: [] });
    expect(h.audits[0]).toMatchObject({
      risk: "flush_outcome_unknown",
      pendingShutdownSave: { count: 1, files: [] },
      pendingRemaining: 1,
      daemonExited: true,
      flushOutcome: "unknown",
    });
  });

  it("classifies native capabilities refusal as daemon_error, not unsupported", async () => {
    const tracker = new PendingSaveTracker();
    const audits: AuditRecord[] = [];
    const handler = makeFlushHandler({
      adapter: {
        async call(call) {
          if (call.command === "system.capabilities") {
            return {
              ok: false,
              command: call.command,
              error: { code: "internal_error", message: "capabilities unavailable" },
            };
          }
          throw new Error("session.flush must not be called");
        },
      },
      tracker,
      waitForExit: async () => true,
      onConfirmedExit: () => {},
      onExitFailure: () => {},
      getContext: () => ({ sessionId: "s" }),
      audit: { async append(record) { audits.push(record); } },
    });

    const env = await handler({});

    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("daemon_error");
    expect(env.code).not.toBe("unsupported_by_daemon");
    expect(env.summary).toContain("capability probe failed");
    expect(audits[0]).toMatchObject({ code: "daemon_error", daemonExited: false });
  });

  it.each([
    [["Patch.esp"], 1],
    [[], 0],
  ])("retries failed flush exit confirmation and clears tracker for pending case %#", async (remaining, count) => {
    const tracker = new PendingSaveTracker();
    tracker.observePostFlushRemaining(remaining, count);
    const lastFlush: FlushSummary = {
      status: "partial",
      outcome: "known",
      force: false,
      flushed: { attempted: 1, renamed: count === 0 ? 1 : 0, failed: count },
      pendingRemaining: remaining,
      pendingRemainingCount: count,
      daemonExited: false,
      daemonPid: 42,
      at: "2026-08-11T00:00:00.000Z",
    };
    const onConfirmedExit = vi.fn();

    const updated = await retryFailedFlushExit({
      waitForExit: async (timeoutMs) => timeoutMs === 1_000,
      tracker,
      lastFlush,
      timeoutMs: 1_000,
      onConfirmedExit,
    });

    expect(updated).toEqual({ ...lastFlush, daemonExited: true });
    expect(tracker.snapshot()).toEqual({ count: 0, files: [] });
    expect(onConfirmedExit).toHaveBeenCalledWith({ ...lastFlush, daemonExited: true });
  });

  it("leaves failed flush state untouched when retry still cannot confirm exit", async () => {
    const tracker = new PendingSaveTracker();
    tracker.observePostFlushRemaining(["Patch.esp"], 1);
    const lastFlush: FlushSummary = {
      status: "partial",
      outcome: "known",
      force: false,
      flushed: { attempted: 1, renamed: 0, failed: 1 },
      pendingRemaining: ["Patch.esp"],
      pendingRemainingCount: 1,
      daemonExited: false,
      daemonPid: 42,
      at: "2026-08-11T00:00:00.000Z",
    };
    const onConfirmedExit = vi.fn();

    const updated = await retryFailedFlushExit({
      waitForExit: async () => false,
      tracker,
      lastFlush,
      onConfirmedExit,
    });

    expect(updated).toBeNull();
    expect(tracker.snapshot()).toEqual({ count: 1, files: ["Patch.esp"] });
    expect(onConfirmedExit).not.toHaveBeenCalled();
  });
});
