import { z } from "zod";
import { ok, refuse } from "../envelope/index.js";
import { KB_ERROR_CODES } from "../envelope/types.js";
import { compareVersions } from "./updates/semver.js";
import { fetchReleaseIndex } from "./updates/release-index.js";
const Args = z.object({ packIds: z.array(z.string().min(1)).optional() }).strict();
export function makeCheckUpdatesTool(opts) {
    return async (rawArgs) => {
        const parsed = Args.safeParse(rawArgs);
        if (!parsed.success) {
            return refuse({
                tool: "bgs_kb_check_updates",
                summary: "Invalid bgs_kb_check_updates request",
                code: KB_ERROR_CODES.INVALID_REQUEST,
                hint: "Call bgs_kb_check_updates with {} or { packIds: [\"bgs-kb-core\"] }.",
                detail: { issues: parsed.error.issues },
                severity: "MEDIUM",
            });
        }
        if (opts.registry.size === 0) {
            return refuse({
                tool: "bgs_kb_check_updates",
                summary: "No KB packs are loaded; cannot check updates",
                code: KB_ERROR_CODES.NOT_LOADED,
                hint: "Run bgs_kb_status to inspect discovery warnings, then install or register at least one pack.",
                severity: "MEDIUM",
            });
        }
        let index;
        try {
            index = await (opts.releaseIndexFetcher ?? (() => fetchReleaseIndex()))();
        }
        catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            const warning = { code: "release_index_fetch_failed", severity: "MEDIUM", message: `Release index fetch failed: ${message}` };
            return ok({
                tool: "bgs_kb_check_updates",
                summary: "Release index unavailable; update check returned partial results",
                data: { updates: [] },
                warnings: [warning],
                status: "partial",
            });
        }
        const requested = parsed.data.packIds ? new Set(parsed.data.packIds) : null;
        const updates = [];
        for (const session of opts.registry.all()) {
            const pack = session.pack;
            if (requested && !requested.has(pack.packId))
                continue;
            const latest = index.packs.find((entry) => entry.packId === pack.packId);
            if (!latest)
                continue;
            updates.push({
                packId: pack.packId,
                currentVersion: pack.version,
                latestVersion: latest.version,
                upgradeAvailable: compareVersions(latest.version, pack.version) > 0,
                breakingChange: compareVersions(latest.minPluginVersion, opts.currentPluginVersion) > 0,
                releaseUrl: latest.releaseUrl,
                sha256: latest.sha256,
                sizeBytes: latest.sizeBytes,
            });
        }
        return ok({
            tool: "bgs_kb_check_updates",
            summary: `${updates.length} pack update entr${updates.length === 1 ? "y" : "ies"} checked`,
            data: { updates },
            status: "completed",
        });
    };
}
//# sourceMappingURL=check-updates.js.map