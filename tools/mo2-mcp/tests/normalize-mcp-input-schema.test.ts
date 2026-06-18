/**
 * Tests for normalizeMcpInputSchema — BUG-13 Lane A + Anthropic top-level
 * union ban (recurrence guard).
 *
 * Background: Zod discriminatedUnion produces top-level {anyOf:[...]}; the
 * MCP wire contract needs {type:"object", ...}. Two earlier shapes were
 * tried and BOTH failed:
 *
 *   Shape v1.2-pre: {type:"object", properties:{}, additionalProperties:true,
 *     anyOf:[...]}
 *   --> Anthropic's tool-use API rejects ANY top-level anyOf/oneOf/allOf in
 *       input_schema and crashes tool registration with
 *         "input_schema does not support oneOf, allOf, or anyOf at the top level"
 *   --> OpenAI also lacked a discriminant anchor and defaulted to the first
 *       branch.
 *
 *   Shape v1.2-mid (BUG-13 Lane A first fix): {type:"object",
 *     properties:{<hoisted-discriminants>}, additionalProperties:true,
 *     anyOf:[...]}
 *   --> Fixed OpenAI argument decoding but still kept anyOf at the top
 *       level, so Anthropic still rejects it.
 *
 * Current fix (Lane A + Anthropic guard): hoist discriminants AND merge
 * non-discriminant branch properties at top level, and DROP the
 * anyOf/oneOf/allOf keyword entirely. The real per-branch validation lives
 * in Zod inside dispatch.ts, not in the wire schema.
 *
 * The "no top-level union keyword" assertion in these tests IS the
 * regression guard. Do not re-add `[kw]: branches` at the top level.
 */
import { describe, it, expect } from "vitest";
import { z } from "zod";
import { zodToJsonSchema } from "zod-to-json-schema";
import { normalizeMcpInputSchema } from "../src/index.js";

describe("normalizeMcpInputSchema", () => {
  it("passes through schemas that already have type=object unchanged", () => {
    const input = {
      type: "object",
      properties: {
        name: { type: "string" },
        enabled: { type: "boolean" },
      },
      required: ["name"],
      additionalProperties: false,
    };
    const out = normalizeMcpInputSchema(input);
    expect(out).toBe(input);
  });

  it("hoists a const-based mode discriminant from anyOf into top-level properties and drops the union keyword", () => {
    const input = {
      anyOf: [
        {
          type: "object",
          properties: {
            mode: { const: "plan" },
            name: { type: "string" },
            enabled: { type: "boolean" },
            profile: { type: "string" },
          },
          required: ["mode", "name", "enabled"],
        },
        {
          type: "object",
          properties: {
            mode: { const: "apply" },
            plan_id: { type: "string" },
            lease_token: { type: "string" },
          },
          required: ["mode", "plan_id", "lease_token"],
        },
      ],
    };
    const out = normalizeMcpInputSchema(input);
    expect(out.type).toBe("object");
    // Discriminant is hoisted with a unioned enum AND every branch's other
    // properties are merged at top level so LLMs see the full surface.
    const props = out.properties as Record<string, unknown>;
    expect(props.mode).toEqual({ enum: ["plan", "apply"] });
    expect(props.name).toEqual({ type: "string" });
    expect(props.enabled).toEqual({ type: "boolean" });
    expect(props.profile).toEqual({ type: "string" });
    expect(props.plan_id).toEqual({ type: "string" });
    expect(props.lease_token).toEqual({ type: "string" });
    expect(out.required).toEqual(["mode"]);
    expect(out.additionalProperties).toBe(true);
    // Anthropic guard: NO top-level union keyword on the wire.
    expect((out as any).anyOf).toBeUndefined();
    expect((out as any).oneOf).toBeUndefined();
    expect((out as any).allOf).toBeUndefined();
  });

  it("hoists when branches mix const and single-value enum for the same discriminant", () => {
    // zod-to-json-schema {target:'openApi3'} emits {type:'string', enum:[X]}
    // for z.literal(X); other producers may emit {const: X}. Both must hoist.
    const input = {
      anyOf: [
        {
          type: "object",
          properties: {
            mode: { type: "string", enum: ["plan"] },
            name: { type: "string" },
          },
          required: ["mode", "name"],
        },
        {
          type: "object",
          properties: {
            mode: { const: "apply" },
            plan_id: { type: "string" },
          },
          required: ["mode", "plan_id"],
        },
      ],
    };
    const out = normalizeMcpInputSchema(input);
    const props = out.properties as Record<string, unknown>;
    expect(props.mode).toEqual({ type: "string", enum: ["plan", "apply"] });
    expect(out.required).toEqual(["mode"]);
  });

  it("merges branch properties at top level even when branches share no const/enum discriminant", () => {
    const input = {
      anyOf: [
        {
          type: "object",
          properties: {
            name: { type: "string" },
          },
          required: ["name"],
        },
        {
          type: "object",
          properties: {
            plan_id: { type: "string" },
          },
          required: ["plan_id"],
        },
      ],
    };
    const out = normalizeMcpInputSchema(input);
    expect(out.type).toBe("object");
    // No shared discriminant means no `required` array, but every branch
    // field is still visible at top level so LLMs can fill them.
    const props = out.properties as Record<string, unknown>;
    expect(props.name).toEqual({ type: "string" });
    expect(props.plan_id).toEqual({ type: "string" });
    expect(out.additionalProperties).toBe(true);
    expect(out.required).toBeUndefined();
    // Anthropic guard: NO top-level union keyword on the wire.
    expect((out as any).anyOf).toBeUndefined();
    expect((out as any).oneOf).toBeUndefined();
    expect((out as any).allOf).toBeUndefined();
  });

  it("DROPS top-level anyOf/oneOf/allOf entirely (Anthropic regression guard)", () => {
    // This test guards the recurring regression: previous fixes preserved
    // `anyOf` at the top level, which crashes Anthropic's tool-use API
    // registration with
    //   "input_schema does not support oneOf, allOf, or anyOf at the top level"
    // The wire schema must stay union-free; per-branch validation lives in
    // Zod inside dispatch.ts. If this test fails, do NOT delete the
    // assertions — fix the function instead.
    for (const kw of ["anyOf", "oneOf", "allOf"] as const) {
      const input = {
        [kw]: [
          {
            type: "object",
            properties: { mode: { const: "plan" }, name: { type: "string" } },
            required: ["mode", "name"],
          },
          {
            type: "object",
            properties: { mode: { const: "apply" }, plan_id: { type: "string" } },
            required: ["mode", "plan_id"],
          },
        ],
      };
      const out = normalizeMcpInputSchema(input);
      expect(out.type, `${kw} should produce type:object`).toBe("object");
      expect((out as any).anyOf, `${kw} → must drop top-level anyOf`).toBeUndefined();
      expect((out as any).oneOf, `${kw} → must drop top-level oneOf`).toBeUndefined();
      expect((out as any).allOf, `${kw} → must drop top-level allOf`).toBeUndefined();
    }
  });

  it("only marks the hoisted discriminant required when it is required in every branch", () => {
    // Branch A requires mode; Branch B does not. Hoist the property (still a
    // useful anchor) but DO NOT force it required at top level — that would
    // reject valid Branch-B inputs that legitimately omit mode.
    const input = {
      anyOf: [
        {
          type: "object",
          properties: {
            mode: { const: "plan" },
            name: { type: "string" },
          },
          required: ["mode", "name"],
        },
        {
          type: "object",
          properties: {
            mode: { const: "apply" },
            plan_id: { type: "string" },
          },
          required: ["plan_id"],
        },
      ],
    };
    const out = normalizeMcpInputSchema(input);
    const props = out.properties as Record<string, unknown>;
    expect(props.mode).toEqual({ enum: ["plan", "apply"] });
    // mode is hoisted but not required at top level (B doesn't require it)
    expect(out.required).toBeUndefined();
    // Anthropic guard.
    expect((out as any).anyOf).toBeUndefined();
  });

  it("hoists every property that is a const/enum-single literal in every branch (multi-discriminant)", () => {
    const input = {
      anyOf: [
        {
          type: "object",
          properties: {
            mode: { const: "plan" },
            action: { const: "create" },
            name: { type: "string" },
          },
          required: ["mode", "action", "name"],
        },
        {
          type: "object",
          properties: {
            mode: { const: "apply" },
            action: { const: "delete" },
            plan_id: { type: "string" },
          },
          required: ["mode", "action", "plan_id"],
        },
      ],
    };
    const out = normalizeMcpInputSchema(input);
    const props = out.properties as Record<string, unknown>;
    expect(props.mode).toEqual({ enum: ["plan", "apply"] });
    expect(props.action).toEqual({ enum: ["create", "delete"] });
    // Non-discriminant fields are also merged through.
    expect(props.name).toEqual({ type: "string" });
    expect(props.plan_id).toEqual({ type: "string" });
    expect(out.required).toEqual(["mode", "action"]);
    // Anthropic guard.
    expect((out as any).anyOf).toBeUndefined();
  });

  // ---------- BUG-27 — recursive nested union flatten ----------
  //
  // The fix surfaces nested anyOf/oneOf/allOf branches into the same flat
  // list before discriminant extraction and property merge. Without it,
  // Zod's z.union([z.discriminatedUnion(...), applyShape]) produces a
  // top-level {anyOf:[{oneOf:[v1,v2,v3]}, applyShape]} whose inner
  // {oneOf:[...]} envelope has no .properties → the merge loop only saw
  // applyShape's fields and the inner variants were invisible to the LLM.

  it("BUG-27: flattens nested anyOf inside an anyOf branch (envelope branch has no own properties)", () => {
    const input = {
      anyOf: [
        {
          anyOf: [
            {
              type: "object",
              properties: {
                mode: { const: "plan" },
                action: { const: "add" },
                entry: { type: "object" },
              },
              required: ["mode", "action", "entry"],
            },
            {
              type: "object",
              properties: {
                mode: { const: "plan" },
                action: { const: "edit" },
                title: { type: "string" },
              },
              required: ["mode", "action", "title"],
            },
          ],
        },
        {
          type: "object",
          properties: {
            mode: { const: "apply" },
            plan_id: { type: "string" },
          },
          required: ["mode", "plan_id"],
        },
      ],
    };
    const out = normalizeMcpInputSchema(input);
    expect(out.type).toBe("object");
    const props = out.properties as Record<string, unknown>;
    // mode present in EVERY flattened branch with a literal value → full discriminant, required
    expect(props.mode).toEqual({ enum: ["plan", "apply"] });
    // action present in 2 of 3 flattened branches with const literals → partial discriminant, unioned, NOT required
    expect(props.action).toEqual({ enum: ["add", "edit"] });
    // Non-discriminant per-branch fields visible at top level
    expect(props.entry).toEqual({ type: "object" });
    expect(props.title).toEqual({ type: "string" });
    expect(props.plan_id).toEqual({ type: "string" });
    expect(out.required).toEqual(["mode"]);
    // Anthropic guard
    expect((out as any).anyOf).toBeUndefined();
    expect((out as any).oneOf).toBeUndefined();
    expect((out as any).allOf).toBeUndefined();
  });

  it("BUG-27: flattens nested oneOf inside an anyOf branch (mixed union keywords)", () => {
    const input = {
      anyOf: [
        {
          oneOf: [
            {
              type: "object",
              properties: {
                mode: { const: "plan" },
                action: { const: "add" },
              },
              required: ["mode", "action"],
            },
            {
              type: "object",
              properties: {
                mode: { const: "plan" },
                action: { const: "remove" },
              },
              required: ["mode", "action"],
            },
          ],
        },
        {
          type: "object",
          properties: {
            mode: { const: "apply" },
            plan_id: { type: "string" },
          },
          required: ["mode", "plan_id"],
        },
      ],
    };
    const out = normalizeMcpInputSchema(input);
    const props = out.properties as Record<string, unknown>;
    expect(props.mode).toEqual({ enum: ["plan", "apply"] });
    // action in 2 of 3 flattened branches as const → partial hoist, unioned
    expect(props.action).toEqual({ enum: ["add", "remove"] });
    expect(props.plan_id).toEqual({ type: "string" });
    expect(out.required).toEqual(["mode"]);
    // Anthropic guard
    expect((out as any).anyOf).toBeUndefined();
    expect((out as any).oneOf).toBeUndefined();
    expect((out as any).allOf).toBeUndefined();
  });

  it("BUG-27: when a branch has BOTH its own properties AND a nested union, the union is expanded and the parent's own properties are dropped (rare; locked-in policy)", () => {
    // This case is not produced by current Zod-derived shapes in this repo.
    // It is locked in here so a future refactor has to deliberately decide
    // whether to change policy. Today: flatten the union; drop the parent.
    const input = {
      anyOf: [
        {
          type: "object",
          properties: { dropped: { type: "string" } },
          anyOf: [
            {
              type: "object",
              properties: { mode: { const: "plan" }, name: { type: "string" } },
              required: ["mode", "name"],
            },
            {
              type: "object",
              properties: { mode: { const: "apply" }, plan_id: { type: "string" } },
              required: ["mode", "plan_id"],
            },
          ],
        },
        {
          type: "object",
          properties: { sibling: { type: "string" } },
          required: ["sibling"],
        },
      ],
    };
    const out = normalizeMcpInputSchema(input);
    const props = out.properties as Record<string, unknown>;
    // Parent envelope's `dropped` is NOT visible (policy choice)
    expect(props.dropped).toBeUndefined();
    // Flattened inner branches' fields ARE visible
    expect(props.mode).toBeDefined();
    expect(props.name).toEqual({ type: "string" });
    expect(props.plan_id).toEqual({ type: "string" });
    // Sibling outer branch's field is also visible
    expect(props.sibling).toEqual({ type: "string" });
    // mode only in 2 of 3 flattened branches (sibling branch has no mode) → partial hoist, NOT required
    expect((props.mode as Record<string, unknown>).enum).toEqual(["plan", "apply"]);
    expect(out.required).toBeUndefined();
    // Anthropic guard
    expect((out as any).anyOf).toBeUndefined();
    expect((out as any).oneOf).toBeUndefined();
    expect((out as any).allOf).toBeUndefined();
  });

  it("BUG-27: mo2_configure_executable Zod-derived shape produces complete top-level properties", () => {
    // This is the real bug shape: z.union([z.discriminatedUnion(...), applyShape]).
    // zodToJsonSchema with target:'openApi3' (the same target index.ts uses)
    // emits {anyOf:[{oneOf:[v1,v2,v3]}, applyShape]} (or similar nested form).
    // After our fix, every per-branch field surfaces at top level so the
    // LLM can construct any of the four legal call shapes through the
    // OpenCode tool-calling wire schema.
    const entrySchema = z.object({
      title: z.string().min(1),
      binary: z.string().min(1),
    });
    const updatesSchema = z.object({
      title: z.string().min(1).optional(),
    });
    const planSchema = z.discriminatedUnion("action", [
      z.object({
        mode: z.literal("plan"),
        action: z.literal("add"),
        entry: entrySchema,
      }),
      z.object({
        mode: z.literal("plan"),
        action: z.literal("edit"),
        title: z.string().min(1),
        updates: updatesSchema,
      }),
      z.object({
        mode: z.literal("plan"),
        action: z.literal("remove"),
        title: z.string().min(1),
      }),
    ]);
    const inputSchema = z.union([
      planSchema,
      z.object({
        mode: z.literal("apply"),
        plan_id: z.string().min(1),
        lease_token: z.string().min(1),
      }),
    ]);
    const raw = zodToJsonSchema(inputSchema, { target: "openApi3" }) as Record<string, unknown>;
    const out = normalizeMcpInputSchema(raw);
    expect(out.type).toBe("object");
    const props = out.properties as Record<string, unknown>;
    // mode appears in EVERY flattened branch (3 plan variants + 1 apply) → full discriminant
    const mode = props.mode as Record<string, unknown>;
    expect(mode).toBeDefined();
    expect(mode.enum).toEqual(expect.arrayContaining(["plan", "apply"]));
    // action appears in 3 of 4 flattened branches → partial discriminant, NOT required
    const action = props.action as Record<string, unknown>;
    expect(action).toBeDefined();
    expect((action.enum as unknown[]).slice().sort()).toEqual(["add", "edit", "remove"]);
    // Non-discriminant fields visible at top level
    expect(props.entry).toBeDefined();
    expect(props.title).toBeDefined();
    expect(props.updates).toBeDefined();
    expect(props.plan_id).toBeDefined();
    expect(props.lease_token).toBeDefined();
    // mode required (in every branch's required); action NOT required (absent from apply branch)
    const required = out.required as string[];
    expect(required).toContain("mode");
    expect(required).not.toContain("action");
    // additionalProperties true so branch-specific fields not yet enumerated remain accepted
    expect(out.additionalProperties).toBe(true);
    // Anthropic regression guard
    expect((out as any).anyOf).toBeUndefined();
    expect((out as any).oneOf).toBeUndefined();
    expect((out as any).allOf).toBeUndefined();
  });
});
