import { describe, expect, it } from "vitest";
import type { BoundContext } from "../src/binding.js";
import {
  computeConflictDelta,
  computeConflictPreview,
  computeRemovedPreview,
  type ConflictDelta,
  type ConflictPreview,
  type ConflictPreviewRemoved,
  type SidecarReport,
} from "../src/conflict-preview.js";

function _report(overrides: Array<{ mod: string; files: number }> = []): SidecarReport {
  return {
    mod: "TargetMod",
    total_files: 3,
    files_winning: 1,
    files_losing: 1,
    files_unique: 1,
    overridden_by: [
      { mod: "WinnerA", files: 10 },
      { mod: "WinnerB", files: 9 },
      { mod: "WinnerC", files: 8 },
      { mod: "WinnerD", files: 7 },
      { mod: "WinnerE", files: 6 },
      { mod: "WinnerF", files: 5 },
    ],
    overrides,
    winners_by_file: {
      "textures/a.dds": "WinnerA",
      "textures/b.dds": "TargetMod",
      "textures/c.dds": "TargetMod",
    },
  };
}

function _assertNoHint(value: unknown): void {
  expect(JSON.stringify(value)).not.toContain("\"hint\"");
}

describe("conflict preview helpers", () => {
  it("computeConflictPreview caps top overridden_by and overrides to 5", async () => {
    const calls: Array<{ method: string; params: unknown }> = [];
    const ctx = {
      config: { mo2Root: "D:/MO2" },
      sidecar: {
        call: async (method: string, params: unknown) => {
          calls.push({ method, params });
          return _report([
            { mod: "LoserA", files: 20 },
            { mod: "LoserB", files: 19 },
            { mod: "LoserC", files: 18 },
            { mod: "LoserD", files: 17 },
            { mod: "LoserE", files: 16 },
            { mod: "LoserF", files: 15 },
          ]);
        },
      },
    } as unknown as BoundContext;

    const preview = await computeConflictPreview("TargetMod", ctx, "Default");

    expect(calls[0]?.method).toBe("assets.report_for_mod");
    expect(calls[0]?.params).toMatchObject({ mod_name: "TargetMod" });
    expect((calls[0]?.params as { profile_dir: string }).profile_dir).toMatch(/[\\/]profiles[\\/]Default$/);
    expect(preview.top_overridden_by.map((entry) => entry.mod)).toEqual([
      "WinnerA",
      "WinnerB",
      "WinnerC",
      "WinnerD",
      "WinnerE",
    ]);
    expect(preview.top_overrides.map((entry) => entry.mod)).toEqual([
      "LoserA",
      "LoserB",
      "LoserC",
      "LoserD",
      "LoserE",
    ]);
    expect(preview.files_total).toBe(3);
    _assertNoHint(preview);
  });

  it("computeConflictDelta zero case returns message and no hint", () => {
    const pre = _report();
    const post = { ...pre, winners_by_file: { ...pre.winners_by_file } };

    const delta = computeConflictDelta(pre, post);

    expect(delta).toEqual({
      files_winner_changed: 0,
      newly_winning: 0,
      newly_losing: 0,
      affected_mods: [],
      message: "No conflict winner changes from this mutation",
    });
    expect("hint" in delta).toBe(false);
    _assertNoHint(delta);
  });

  it("computeConflictDelta counts newly winning and newly losing files", () => {
    const pre: SidecarReport = {
      ..._report(),
      winners_by_file: {
        "textures/now-winning.dds": "OtherBefore",
        "textures/now-losing.dds": "TargetMod",
        "textures/still-winning.dds": "TargetMod",
        "textures/unchanged-other.dds": "OtherBefore",
      },
    };
    const post: SidecarReport = {
      ..._report(),
      winners_by_file: {
        "textures/now-winning.dds": "TargetMod",
        "textures/now-losing.dds": "OtherAfter",
        "textures/still-winning.dds": "TargetMod",
        "textures/unchanged-other.dds": "OtherBefore",
      },
    };

    const delta = computeConflictDelta(pre, post);

    expect(delta.files_winner_changed).toBe(2);
    expect(delta.newly_winning).toBe(1);
    expect(delta.newly_losing).toBe(1);
    expect(delta.affected_mods).toEqual([
      { mod: "OtherBefore", flipped_files: 1, direction: "now_loses_to_us" },
      { mod: "OtherAfter", flipped_files: 1, direction: "now_beats_us" },
    ]);
    _assertNoHint(delta);
  });

  it("computeRemovedPreview reports files no longer provided and top affected mods", () => {
    const removed = computeRemovedPreview(_report([
      { mod: "LoserA", files: 20 },
      { mod: "LoserB", files: 19 },
      { mod: "LoserC", files: 18 },
      { mod: "LoserD", files: 17 },
      { mod: "LoserE", files: 16 },
      { mod: "LoserF", files: 15 },
    ]));

    expect(removed).toEqual({
      removed: true,
      files_no_longer_provided: 3,
      top_affected: [
        { mod: "LoserA", files: 20 },
        { mod: "LoserB", files: 19 },
        { mod: "LoserC", files: 18 },
        { mod: "LoserD", files: 17 },
        { mod: "LoserE", files: 16 },
      ],
    });
    _assertNoHint(removed);
  });

  it("regression: no returned preview or delta shape carries hint", () => {
    const preview: ConflictPreview = {
      mod: "TargetMod",
      files_total: 0,
      files_winning: 0,
      files_losing: 0,
      files_unique: 0,
      top_overridden_by: [],
      top_overrides: [],
    };
    const delta: ConflictDelta = computeConflictDelta(_report(), _report());
    const removed: ConflictPreviewRemoved = computeRemovedPreview(_report());

    _assertNoHint(preview);
    _assertNoHint(delta);
    _assertNoHint(removed);
  });
});
