import type { EnvelopeOk, EnvelopeRefusal, Warning } from "./types.js";
export declare function ok<T>(input: Omit<EnvelopeOk<T>, "ok" | "warnings"> & {
    warnings?: Warning[];
}): EnvelopeOk<T>;
export declare function refuse(input: Omit<EnvelopeRefusal, "ok" | "warnings"> & {
    warnings?: Warning[];
}): EnvelopeRefusal;
export type { Envelope, EnvelopeOk, EnvelopeRefusal, KbErrorCode, Severity, Warning } from "./types.js";
export { KB_ERROR_CODES } from "./types.js";
