/**
 * Closed enum of KB-MCP error codes per spec §9.4.
 *
 * Some codes apply to specific tools (e.g. record_not_found → bgs_kb_get).
 * Tools should only emit codes from this list; new codes require a spec amendment.
 */
export declare const KB_ERROR_CODES: {
    readonly NOT_LOADED: "not_loaded";
    readonly RECORD_NOT_FOUND: "record_not_found";
    readonly PACK_ID_COLLISION: "pack_id_collision";
    readonly SCHEMA_VERSION_UNSUPPORTED: "schema_version_unsupported";
    readonly MIN_PLUGIN_VERSION_UNMET: "min_plugin_version_unmet";
    readonly PACK_INTEGRITY_FAILED: "pack_integrity_failed";
    readonly VARIANT_DELETION_UNMATCHED: "variant_deletion_unmatched";
    readonly DOWNLOAD_FAILED: "download_failed";
    readonly INVALID_REQUEST: "invalid_request";
    readonly INTERNAL_ERROR: "internal_error";
};
export type KbErrorCode = (typeof KB_ERROR_CODES)[keyof typeof KB_ERROR_CODES];
export type Severity = "MEDIUM" | "HIGH" | "CRITICAL";
export interface Warning {
    code: string;
    message: string;
    severity: "MEDIUM" | "HIGH";
}
export interface EnvelopeBase {
    tool: string;
    summary: string;
    warnings: Warning[];
}
export interface EnvelopeOk<T = unknown> extends EnvelopeBase {
    ok: true;
    data: T;
    status?: "completed" | "partial";
}
export interface EnvelopeRefusal extends EnvelopeBase {
    ok: false;
    code: KbErrorCode;
    hint?: string;
    detail?: Record<string, unknown>;
    severity?: Severity;
}
export type Envelope<T = unknown> = EnvelopeOk<T> | EnvelopeRefusal;
