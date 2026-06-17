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
});
