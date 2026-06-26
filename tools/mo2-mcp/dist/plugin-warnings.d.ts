/**
 * Plugin-warnings helper.
 *
 * Wraps the broker's plugins.missing_masters call with the stale-broker
 * fallback per memory rule BUG-23. Always returns a shape — never throws.
 * Used by:
 *   - mo2_plugin_warnings standalone tool
 *   - mo2_toggle_plugin auto-poll (apply path)
 *   - mo2_toggle_mod auto-poll (apply path)
 *   - mo2_install auto-poll (apply path, BUG-E pathway)
 *   - mo2_reinstall_mod auto-poll (apply path)
 */
import type { PipeClient } from "./pipe-client.js";
export interface PluginWarning {
    plugin: string;
    missingMasters: string[];
    enabledMasters: string[];
    declaredMasters: string[];
}
export interface PluginWarningsResult {
    warnings: PluginWarning[];
    scannedCount: number;
    enabledCount: number;
    pollFailed?: string;
}
export declare function pollPluginWarnings(pipeClient: PipeClient, names?: string[]): Promise<PluginWarningsResult>;
