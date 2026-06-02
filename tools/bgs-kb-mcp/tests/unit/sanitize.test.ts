import { expect, test } from "vitest";

import { sanitizeFtsQuery } from "../../src/tools/sanitize.js";

test("plain words pass through unchanged", () => {
  expect(sanitizeFtsQuery("loose archive plugins")).toBe("loose archive plugins");
});

test("quoted phrases are preserved", () => {
  expect(sanitizeFtsQuery('"plugins.txt asterisk"')).toBe('"plugins.txt asterisk"');
});

test("bare dot-bearing tokens are wrapped as phrases", () => {
  expect(sanitizeFtsQuery("plugins.txt")).toBe('"plugins.txt"');
});

test("special punctuation is stripped", () => {
  expect(sanitizeFtsQuery("query?")).toBe("query");
  expect(sanitizeFtsQuery("query!")).toBe("query");
});

test("empty string sanitizes to empty string", () => {
  expect(sanitizeFtsQuery("   ")).toBe("");
});

test("mixed query preserves phrases, wraps dotted tokens, and strips FTS operators", () => {
  expect(sanitizeFtsQuery('-plugins.txt "load order" (FormID):* ^archive')).toBe('"plugins.txt" "load order" FormID archive');
});
