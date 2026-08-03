import { describe, expect, it } from "vitest";
import {
  PendingSaveTracker,
  pendingSaveLifecycleRisk,
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
});
