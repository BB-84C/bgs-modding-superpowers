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
/**
 * Per-element dependency-evaluation result. Populated by the sidecar when an
 * mo2_state was supplied to fomod.parse_choices; otherwise the field is
 * omitted (NOT `{met:true, missing:[]}`) on options/pages and not present at
 * the top level. `missing` carries human-readable failure descriptions like
 * `"file CBBE.esp must be Active (was Missing)"`.
 */
export interface FomodDependencyStatus {
  met: boolean;
  missing: string[];
}

export interface FomodTreeShape {
  fomod_name: string;
  fomod_version: string | null;
  /**
   * Lane V3 FOMOD-EXT: when the FOMOD declares conditional pages, conditional
   * file installs, or dynamic option types, this carries a human-readable note
   * explaining that the static page tree returned here may diverge from the
   * actual wizard flow. `null` when no conditional flow was detected. Always
   * present in v1.3+ responses; absent (or null) is fine for older callers.
   */
  conditional_pages_note?: string | null;
  /**
   * Lane V3 FOMOD-EXT: present when mo2_state was supplied. Reports whether
   * the FOMOD's <moduleDependencies> hold against current MO2 state. When
   * met=false the installer will refuse to run (resolve_files raises
   * invalid_choices).
   */
  module_dependencies_status?: FomodDependencyStatus;
  pages: Array<{
    name: string;
    /** Present when mo2_state was supplied; reflects page <visible> conditions. */
    dependencies_status?: FomodDependencyStatus;
    groups: Array<{
      name: string;
      type: string;
      options: Array<{
        name: string;
        description: string;
        image: string | null;
        /**
         * When mo2_state was supplied and the option's underlying FOMOD type is
         * a <dependencyType>, this is the RESOLVED OptionType given mo2_state
         * (e.g. "Required" / "NotUsable" / "Recommended"). For static-type
         * options it's the declared type. Without mo2_state it's the declared
         * type (Type instances surface as their default name).
         */
        type: string;
        /**
         * Present when mo2_state was supplied. For static-type options it is
         * always {met:true, missing:[]}. For <dependencyType> options it
         * reflects whether the option will be selectable (met=false when
         * resolved type is NotUsable).
         */
        dependencies_status?: FomodDependencyStatus;
      }>;
    }>;
  }>;
}

export class FomodChoicesRequiredError extends Error {
  readonly code: "fomod_choices_required" | "fomod_choices_required_for_reinstall";
  readonly details: { fomod_tree: FomodTreeShape };

  constructor(args: {
    code: "fomod_choices_required" | "fomod_choices_required_for_reinstall";
    message: string;
    fomod_tree: FomodTreeShape;
  }) {
    super(args.message);
    this.name = "FomodChoicesRequiredError";
    this.code = args.code;
    this.details = { fomod_tree: args.fomod_tree };
  }
}
