import type { EnvelopeOk, EnvelopeRefusal, Warning } from "./types.js";

export function ok<T>(input: Omit<EnvelopeOk<T>, "ok" | "warnings"> & { warnings?: Warning[] }): EnvelopeOk<T> {
  return { ...input, ok: true, warnings: input.warnings ?? [] };
}

export function refuse(input: Omit<EnvelopeRefusal, "ok" | "warnings"> & { warnings?: Warning[] }): EnvelopeRefusal {
  return { ...input, ok: false, warnings: input.warnings ?? [] };
}

export type { Envelope, EnvelopeOk, EnvelopeRefusal, KbErrorCode, Severity, Warning } from "./types.js";
export { KB_ERROR_CODES } from "./types.js";
