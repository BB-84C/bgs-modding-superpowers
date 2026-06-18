import type { ToolContext } from "./types.js";
export interface Mo2FomodState {
    enabled_plugins: string[];
    game_version: string | null;
    provided_files: string[];
}
/**
 * Read enabled plugins from `<profile>/plugins.txt`, game version (best-effort)
 * from `ModOrganizer.ini`, and return the shape the sidecar expects.
 *
 * Failures (missing profile dir, malformed INI) downgrade to an empty state
 * rather than throwing — the sidecar treats an empty state as "no dependency
 * info" and parse_choices still works, just without dependencies_status fields.
 */
export declare function gatherMo2FomodState(ctx: ToolContext, profile: string): Promise<Mo2FomodState>;
