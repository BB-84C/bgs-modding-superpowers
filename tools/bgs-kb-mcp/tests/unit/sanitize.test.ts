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

test("internal-hyphen tokens (letter-letter) are wrapped to avoid FTS5 column-ref crash", () => {
  expect(sanitizeFtsQuery("mis-attribution")).toBe('"mis-attribution"');
  expect(sanitizeFtsQuery("anti-checklist BB84-philosophy")).toBe('"anti-checklist" "BB84-philosophy"');
});

test("internal-hyphen tokens (letter-digit) are wrapped (CP-1252, UTF-8)", () => {
  expect(sanitizeFtsQuery("CP-1252 UTF-8")).toBe('"CP-1252" "UTF-8"');
});

test("hyphen-bearing tokens mix cleanly with plain tokens", () => {
  expect(sanitizeFtsQuery("hello mis-attribution world")).toBe('hello "mis-attribution" world');
});

test("Unicode (Chinese) bare tokens stay unwrapped", () => {
  expect(sanitizeFtsQuery("汉化 整合包")).toBe("汉化 整合包");
});

test("slash-bearing tokens are wrapped (defensive)", () => {
  expect(sanitizeFtsQuery("Documents/F4SE/log")).toBe('"Documents/F4SE/log"');
});
