import { describe, expect, it } from "vitest";
import {
  dirtyFileNames,
  PendingSaveTracker,
  pendingSaveLifecycleRisk,
  refreshPendingSaveAuthority,
  withPendingShutdownSave,
} from "../../src/pending-save.js";

describe("pending shutdown save guard", () => {
  it("tracks the daemon's exact pending-save fields even when dirty:false", () => {
    const tracker = new PendingSaveTracker();

    tracker.observeSuccessfulSave({
      savedFilesNow: [],
      savedFilesPendingShutdown: [{ name: "Patch.esp", fileName: "Patch.esp" }],
      savedNowCount: 0,
      savePendingShutdownCount: 1,
      dirtyState: { dirty: false, dirtyFiles: [], unsavedChangeCount: 0 },
    });

    expect(tracker.snapshot()).toEqual({
      count: 1,
      files: [{ name: "Patch.esp", fileName: "Patch.esp" }],
    });
    expect(withPendingShutdownSave({ dirty: false }, tracker.snapshot())).toEqual({
      dirty: false,
      pendingShutdownSave: {
        count: 1,
        files: [{ name: "Patch.esp", fileName: "Patch.esp" }],
      },
    });
  });

  it("refuses normal stop and restart while a save is pending shutdown", () => {
    const tracker = new PendingSaveTracker();
    tracker.observeSuccessfulSave({
      savedFilesPendingShutdown: [{ name: "Patch.esp" }],
      savedNowCount: 0,
      savePendingShutdownCount: 1,
    });

    expect(pendingSaveLifecycleRisk("stop", tracker.snapshot(), false)).toMatchObject({
      code: "pending_save",
      severity: "CRITICAL",
      data: { pendingShutdownSave: { count: 1, files: [{ name: "Patch.esp" }] } },
    });
    expect(pendingSaveLifecycleRisk("restart", tracker.snapshot(), false)).toMatchObject({
      code: "pending_save",
      severity: "CRITICAL",
    });
  });

  it("keeps force:true as an explicit, auditable abandonment", () => {
    const tracker = new PendingSaveTracker();
    tracker.observeSuccessfulSave({
      savedFilesPendingShutdown: [{ name: "Patch.esp" }],
      savedNowCount: 0,
      savePendingShutdownCount: 1,
    });

    expect(pendingSaveLifecycleRisk("stop", tracker.snapshot(), true)).toEqual({
      abandonment: true,
      risk: "pending_shutdown_save_may_be_lost",
      pendingShutdownSave: { count: 1, files: [{ name: "Patch.esp" }] },
    });
  });

  it("keeps normal no-pending saves lifecycle-compatible", () => {
    const tracker = new PendingSaveTracker();
    tracker.observeSuccessfulSave({
      savedFilesNow: [{ name: "Patch.esp" }],
      savedFilesPendingShutdown: [],
      savedNowCount: 1,
      savePendingShutdownCount: 0,
    });

    expect(tracker.snapshot()).toEqual({ count: 0, files: [] });
    expect(pendingSaveLifecycleRisk("stop", tracker.snapshot(), false)).toBeNull();
  });

  it("does not clear prior pending state from dirty:false or an unrelated no-pending save", () => {
    const tracker = new PendingSaveTracker();
    tracker.observeSuccessfulSave({
      savedFilesPendingShutdown: [{ name: "Patch.esp" }],
      savedNowCount: 0,
      savePendingShutdownCount: 1,
    });
    tracker.observeSuccessfulSave({
      savedFilesNow: [{ name: "Other.esp" }],
      savedFilesPendingShutdown: [],
      savedNowCount: 1,
      savePendingShutdownCount: 0,
      dirtyState: { dirty: false },
    });

    expect(tracker.snapshot()).toEqual({ count: 1, files: [{ name: "Patch.esp" }] });
  });

  it("uses savePendingShutdownCount when summaries are plain strings or absent", () => {
    const tracker = new PendingSaveTracker();
    tracker.observeSuccessfulSave({
      savedFilesPendingShutdown: ["Patch.esp"],
      savePendingShutdownCount: 1,
    });
    tracker.observeSuccessfulSave({
      savePendingShutdownCount: 2,
    });

    expect(tracker.snapshot()).toEqual({
      count: 2,
      files: ["Patch.esp"],
    });
  });

  it("does not inflate an anonymous pending count when the same save is observed repeatedly", () => {
    const tracker = new PendingSaveTracker();
    const response = {
      savedFilesPendingShutdown: [null],
      savePendingShutdownCount: 1,
    };

    tracker.observeSuccessfulSave(response);
    tracker.observeSuccessfulSave(response);

    expect(tracker.snapshot()).toEqual({ count: 1, files: [] });
  });

  it("projects and enforces pending state even when the daemon is not ready", () => {
    const tracker = new PendingSaveTracker();
    tracker.observeSuccessfulSave({ savePendingShutdownCount: 1 });

    expect(withPendingShutdownSave({ status: "starting", responsive: false }, tracker.snapshot()))
      .toMatchObject({
        status: "starting",
        responsive: false,
        pendingShutdownSave: { count: 1, files: [] },
      });
    expect(pendingSaveLifecycleRisk("restart", tracker.snapshot(), false)).toMatchObject({
      code: "pending_save",
      data: { pendingShutdownSave: { count: 1, files: [] } },
    });
  });

  it("authoritative pending readback replaces stale local knowledge, including with zero", () => {
    const tracker = new PendingSaveTracker();
    tracker.observeSuccessfulSave({
      savedFilesPendingShutdown: [{ name: "Old.esp" }],
      savePendingShutdownCount: 1,
    });

    expect(tracker.observeDirtyState({
      pendingShutdownFiles: [],
      pendingShutdownCount: 0,
    })).toBe(true);
    expect(tracker.snapshot()).toEqual({ count: 0, files: [] });

    tracker.observeSuccessfulSave({ savePendingShutdownCount: 1 });
    tracker.observeDirtyState({
      pendingShutdownFiles: [
        { tempFile: "A.save", file: { name: "A.esp", fileName: "A.esp" } },
        { tempFile: "B.save", file: { name: "B.esp", fileName: "B.esp" } },
      ],
      pendingShutdownCount: 2,
    });
    expect(tracker.snapshot()).toMatchObject({ count: 2 });
    expect(tracker.snapshot().files).toHaveLength(2);
  });

  it("does not clear local state when authoritative fields are incomplete", () => {
    const tracker = new PendingSaveTracker();
    tracker.observeSuccessfulSave({ savePendingShutdownCount: 1 });

    expect(tracker.observeDirtyState({ pendingShutdownCount: 0 })).toBe(false);
    expect(tracker.observeDirtyState({ pendingShutdownFiles: [] })).toBe(false);
    expect(tracker.snapshot()).toEqual({ count: 1, files: [] });
  });

  it("uses a complete session.save dirtyState as authoritative post-save readback", () => {
    const tracker = new PendingSaveTracker();
    tracker.observeSuccessfulSave({ savePendingShutdownCount: 3 });
    tracker.observeSuccessfulSave({
      savedFilesPendingShutdown: [],
      savePendingShutdownCount: 0,
      dirtyState: { pendingShutdownFiles: [], pendingShutdownCount: 0 },
    });
    expect(tracker.snapshot()).toEqual({ count: 0, files: [] });
  });

  it("still accepts authoritative save dirtyState when legacy save counters are absent", () => {
    const tracker = new PendingSaveTracker();
    tracker.observeSuccessfulSave({ savePendingShutdownCount: 1 });
    tracker.observeSuccessfulSave({
      dirtyState: { pendingShutdownFiles: [], pendingShutdownCount: 0 },
    });
    expect(tracker.snapshot()).toEqual({ count: 0, files: [] });
  });

  it.each(["stop", "restart"] as const)("applies authoritative readback before the %s pending gate", (operation) => {
    const tracker = new PendingSaveTracker();
    tracker.observeSuccessfulSave({ savePendingShutdownCount: 1 });
    tracker.observeDirtyState({ pendingShutdownFiles: [], pendingShutdownCount: 0 });
    expect(pendingSaveLifecycleRisk(operation, tracker.snapshot(), false)).toBeNull();

    tracker.observeDirtyState({
      pendingShutdownFiles: [{ file: { name: "New.esp" } }],
      pendingShutdownCount: 1,
    });
    expect(pendingSaveLifecycleRisk(operation, tracker.snapshot(), false)).toMatchObject({ code: "pending_save" });
  });

  it("preserves local fail-closed state when a lifecycle authority probe fails", async () => {
    const tracker = new PendingSaveTracker();
    tracker.observeSuccessfulSave({ savePendingShutdownCount: 1 });
    const adapter = {
      async call() { throw new Error("pipe closed"); },
    };

    const probe = await refreshPendingSaveAuthority(adapter, tracker);
    expect(probe.ok).toBe(false);
    expect(tracker.snapshot()).toEqual({ count: 1, files: [] });
  });

  it("returns a diagnostic Error for an invalid dirty-state result", async () => {
    const tracker = new PendingSaveTracker();
    const probe = await refreshPendingSaveAuthority({
      async call() {
        return { ok: true, command: "session.get_dirty_state", result: "invalid" };
      },
    }, tracker);
    expect(probe.ok).toBe(false);
    if (probe.ok) throw new Error("expected invalid result");
    expect(probe.error).toBeInstanceOf(Error);
    expect((probe.error as Error).message).toContain("object");
  });

  it("authoritatively replaces tracker from validated post-flush remaining state", () => {
    const tracker = new PendingSaveTracker();
    tracker.observeSuccessfulSave({
      savedFilesPendingShutdown: [{ name: "Old.esp" }],
      savePendingShutdownCount: 1,
    });
    tracker.observePostFlushRemaining([], 0);
    expect(tracker.snapshot()).toEqual({ count: 0, files: [] });

    tracker.observePostFlushRemaining(["StillPending.esp"], 1);
    expect(tracker.snapshot()).toEqual({ count: 1, files: ["StillPending.esp"] });
  });

  it("warns that force lifecycle skips pending rename handling", () => {
    const risk = pendingSaveLifecycleRisk("stop", { count: 1, files: [] }, false);
    expect(risk).toMatchObject({ code: "pending_save" });
    if (!risk || !("code" in risk)) throw new Error("expected refusal");
    expect(risk.hint).toContain("hard-terminates");
    expect(risk.hint).toContain("temporary save files");
  });

  it("extracts dirty file names from 0.23 file-summary objects", () => {
    expect(dirtyFileNames([
      { name: "One.esp", fileName: "One.esp" },
      { fileName: "Two.esm" },
      "Legacy.esp",
      {},
    ])).toEqual(["One.esp", "Two.esm", "Legacy.esp"]);
  });
});
