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
};
//# sourceMappingURL=types.js.map