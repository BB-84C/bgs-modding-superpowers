/**
 * Typed error for FOMOD installers that require explicit agent choices.
 *
 * BUG-26 (2026-06-17): mo2_install / mo2_reinstall_mod used to attach the
 * parsed FOMOD tree to a plain Error object as `.fomod_tree`. dispatch.ts then
 * treated it as a generic Error, preserving only e.message and collapsing the
 * agent-facing envelope to `internal_error`. This typed class gives dispatch a
 * stable branch that preserves both the semantic code and the sidecar's real
 * `fomod.parse_choices` tree shape.
 */
export interface FomodTreeShape {
    fomod_name: string;
    fomod_version: string | null;
    pages: Array<{
        name: string;
        groups: Array<{
            name: string;
            type: string;
            options: Array<{
                name: string;
                description: string;
                image: string | null;
                type: string;
            }>;
        }>;
    }>;
}
export declare class FomodChoicesRequiredError extends Error {
    readonly code: "fomod_choices_required" | "fomod_choices_required_for_reinstall";
    readonly details: {
        fomod_tree: FomodTreeShape;
    };
    constructor(args: {
        code: "fomod_choices_required" | "fomod_choices_required_for_reinstall";
        message: string;
        fomod_tree: FomodTreeShape;
    });
}
