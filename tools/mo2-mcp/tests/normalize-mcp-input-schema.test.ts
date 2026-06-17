/**
 * Tests for normalizeMcpInputSchema — BUG-13 Lane A.
 *
 * Background: Zod discriminatedUnion produces top-level {anyOf:[...]}; the
 * MCP wire contract needs {type:"object", ...}. The prior shape wrapped
 * unions as {type:"object", properties:{}, additionalProperties:true,
 * anyOf:[...]}. The empty top-level `properties` gives OpenAI tool-callers
 * (gpt-5.x) no anchor for argument decoding — the model defaults to the
 * first branch's discriminant every time.
 *
 * Fix: hoist any property that exists in every branch as a const or single-
 * value-enum literal into top-level `properties` with a unioned enum. The
 * original anyOf is preserved so branch-by-branch validators keep working.
 *
 * Phase 4-final-beta evidence (claude-opus-4-7 17/17 apply-mode-correct on
 * the prior empty-properties shape) proves the additive hoist is safe for
 * Anthropic tool-callers.
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

  it("hoists a const-based mode discriminant from anyOf into top-level properties", () => {
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
    expect(out.properties).toEqual({
      mode: { enum: ["plan", "apply"] },
    });
    expect(out.required).toEqual(["mode"]);
    expect(out.additionalProperties).toBe(true);
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

  it("falls back to empty properties when branches share no const/enum discriminant", () => {
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
    expect(out.properties).toEqual({});
    expect(out.additionalProperties).toBe(true);
    expect(out.required).toBeUndefined();
    expect((out as any).anyOf).toBe(input.anyOf);
  });

  it("preserves the original anyOf branches verbatim at the top level (regression guard)", () => {
    const input = {
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
    };
    const out = normalizeMcpInputSchema(input);
    // The original branches array must be carried through unchanged so MCP
    // clients that validate branch-by-branch still see the full per-mode
    // shape (including each branch's own const/required mode).
    expect((out as any).anyOf).toBe(input.anyOf);
    expect((out as any).anyOf).toEqual(input.anyOf);
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
    expect(out.properties).toEqual({
      mode: { enum: ["plan", "apply"] },
      action: { enum: ["create", "delete"] },
    });
    expect(out.required).toEqual(["mode", "action"]);
  });
});
