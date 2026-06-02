import { expect, test } from "vitest";

import { ok, refuse } from "../../src/envelope/index.js";

test("ok builds a success envelope with default empty warnings", () => {
  const env = ok({ tool: "bgs_kb_status", summary: "ready", data: { packs: 1 } });

  expect(env).toEqual({ tool: "bgs_kb_status", summary: "ready", data: { packs: 1 }, ok: true, warnings: [] });
});

test("ok preserves warnings and status", () => {
  const env = ok({
    tool: "bgs_kb_query",
    summary: "partial results",
    data: { hits: [] },
    status: "partial",
    warnings: [{ code: "pack_skipped", message: "one pack skipped", severity: "MEDIUM" }],
  });

  expect(env.warnings).toEqual([{ code: "pack_skipped", message: "one pack skipped", severity: "MEDIUM" }]);
  expect(env.status).toBe("partial");
});

test("ok treats explicit undefined warnings as empty warnings", () => {
  const env = ok({ tool: "bgs_kb_get", summary: "found", data: {}, warnings: undefined });

  expect(env.warnings).toEqual([]);
});

test("refuse builds a refusal envelope with code, hint, and default warnings", () => {
  const env = refuse({ tool: "bgs_kb_get", summary: "not found", code: "record_not_found", hint: "Run bgs_kb_query first" });

  expect(env.ok).toBe(false);
  if (env.ok) throw new Error("expected refusal");
  expect(env.code).toBe("record_not_found");
  expect(env.hint).toBe("Run bgs_kb_query first");
  expect(env.warnings).toEqual([]);
});
