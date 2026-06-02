/**
 * Closed enum of KB-MCP error codes per spec §9.4.
 *
 * Some codes apply to specific tools (e.g. record_not_found → bgs_kb_get).
 * Tools should only emit codes from this list; new codes require a spec amendment.
 */
export const KB_ERROR_CODES = {
  NOT_LOADED: "not_loaded",
  RECORD_NOT_FOUND: "record_not_found",
  PACK_ID_COLLISION: "pack_id_collision",
  SCHEMA_VERSION_UNSUPPORTED: "schema_version_unsupported",
  MIN_PLUGIN_VERSION_UNMET: "min_plugin_version_unmet",
  PACK_INTEGRITY_FAILED: "pack_integrity_failed",
  VARIANT_DELETION_UNMATCHED: "variant_deletion_unmatched",
  DOWNLOAD_FAILED: "download_failed",
  INVALID_REQUEST: "invalid_request",
  INTERNAL_ERROR: "internal_error",
} as const;

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
