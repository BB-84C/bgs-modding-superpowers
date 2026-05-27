import { describe, it, expect } from "vitest";
import { z } from "zod";
import { validateArgs } from "../../src/pipeline/validate.js";

const schema = z.object({
  file: z.string().min(1),
  formId: z.string().regex(/^0x[0-9a-fA-F]{8}$/),
});

describe("pipeline.validate", () => {
  it("returns null on a fully valid args object", () => {
    const r = validateArgs(schema, { file: "X.esp", formId: "0x00001234" });
    expect(r).toBeNull();
  });

  it("returns a refusal envelope with detail on bad shape", () => {
    const r = validateArgs(schema, { file: "", formId: "nope" }, { tool: "xedit_find_record" });
    expect(r).not.toBeNull();
    if (!r) throw new Error("expected refusal");
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error("expected refusal");
    expect(r.code).toBe("invalid_request");
    expect(r.detail).toBeDefined();
    expect(r.tool).toBe("xedit_find_record");
  });
});
