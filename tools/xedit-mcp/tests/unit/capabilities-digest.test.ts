import { describe, it, expect } from "vitest";
import { CAPABILITIES_DIGEST, allDigestCommands } from "../../src/capabilities-digest.js";

describe("capabilities digest", () => {
  it("covers all 8 groups", () => {
    const groups = new Set(CAPABILITIES_DIGEST.groups.map((g) => g.name));
    expect(groups).toEqual(
      new Set(["system", "session", "files", "records", "elements", "jobs", "scripts"]),
    );
    expect(CAPABILITIES_DIGEST.groups.length).toBeGreaterThanOrEqual(7);
  });

  it("enumerates the read-only commands needed for Batch 1 (W2 conflict audit)", () => {
    const cmds = new Set(allDigestCommands());
    [
      "system.describe", "system.capabilities",
      "session.get_dirty_state",
      "records.list", "records.find_by_form_id", "records.find_by_editor_id",
      "records.get", "records.winning_override", "records.base_record",
      "records.conflict_status", "records.references", "records.referenced_by",
      "elements.get", "elements.children", "elements.conflict_status",
    ].forEach((c) => expect(cmds.has(c)).toBe(true));
  });

  it("each entry carries minimal metadata for skill use", () => {
    const sample = CAPABILITIES_DIGEST.groups[0].commands[0];
    expect(typeof sample.name).toBe("string");
    expect(typeof sample.summary).toBe("string");
    expect(typeof sample.mutating).toBe("boolean");
  });
});
