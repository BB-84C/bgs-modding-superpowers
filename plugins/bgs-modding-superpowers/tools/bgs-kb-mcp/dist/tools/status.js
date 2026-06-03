import { z } from "zod";
import { ok, refuse } from "../envelope/index.js";
const Args = z.object({}).strict();
function packLabel(packId) {
    return packId ?? "<unknown>";
}
function warningFromSkip(skip) {
    switch (skip.code) {
        case "missing_manifest":
            return { code: skip.code, severity: "MEDIUM", message: `Pack candidate at ${skip.path} has no manifest.json; skipped` };
        case "invalid_manifest_json":
            return { code: skip.code, severity: "HIGH", message: `Pack candidate at ${skip.path} has malformed manifest.json; skipped` };
        case "missing_kb_sqlite":
            return { code: skip.code, severity: "HIGH", message: `Pack ${packLabel(skip.packId)} at ${skip.path} is missing kb.sqlite; skipped` };
        case "schema_version_unsupported":
            return {
                code: skip.code,
                severity: "HIGH",
                message: `Pack ${packLabel(skip.packId)} requires schemaVersion ${skip.packSchemaVersion}; this plugin supports up to ${skip.supportedSchemaVersion}`,
            };
        case "min_plugin_version_unmet":
            return { code: skip.code, severity: "HIGH", message: `Pack ${packLabel(skip.packId)} requires plugin >= ${skip.required}; current is ${skip.current}` };
        case "pack_integrity_failed":
            return {
                code: skip.code,
                severity: "HIGH",
                message: `Pack ${packLabel(skip.packId)} at ${skip.path} failed sha256 verification (expected ${skip.expectedSha256}, got ${skip.actualSha256}); refused`,
            };
    }
}
function warningFromCollision(collision) {
    const paths = collision.paths.map((path) => `${path.root}:${path.packRoot}`).join(", ");
    return {
        code: collision.code,
        severity: "HIGH",
        message: `Pack id collision: ${collision.packId} present at ${collision.paths.length} roots; all refused. Remove duplicates: ${paths}`,
    };
}
function dataFromPack(pack) {
    return {
        packId: pack.packId,
        displayName: pack.displayName,
        version: pack.version,
        schemaVersion: pack.schemaVersion,
        minPluginVersion: pack.minPluginVersion,
        root: pack.root,
        rootPath: pack.rootPath,
        recordCount: pack.manifest.recordCount,
        domains: pack.manifest.domains,
        games: pack.manifest.games,
        integrityOk: pack.integrityOk,
        loadedAt: pack.loadedAt,
    };
}
function summary(packCount, recordCount, warningCount) {
    return `${packCount} packs loaded (${recordCount} records); ${warningCount} warnings`;
}
export function makeStatusTool(opts) {
    return async (rawArgs) => {
        const parsed = Args.safeParse(rawArgs);
        if (!parsed.success) {
            return refuse({
                tool: "bgs_kb_status",
                summary: "Invalid bgs_kb_status request: expected no arguments",
                code: "invalid_request",
                hint: "Call bgs_kb_status with an empty object: {}",
                detail: { issues: parsed.error.issues },
                severity: "MEDIUM",
            });
        }
        const warnings = [...opts.discovery.skipped.map(warningFromSkip), ...opts.discovery.collisions.map(warningFromCollision)];
        if (opts.discovery.packs.length !== opts.registry.size) {
            warnings.push({
                code: "internal_inconsistency",
                severity: "MEDIUM",
                message: `Internal inconsistency: discovery loaded ${opts.discovery.packs.length} pack(s), registry has ${opts.registry.size} open session(s)`,
            });
        }
        const packs = opts.discovery.packs.map(dataFromPack);
        const totalRecordCount = packs.reduce((sum, pack) => sum + pack.recordCount, 0);
        const cacheRoot = opts.discovery.rootsScanned.find((root) => root.root === "cache")?.rootPath ?? "";
        const userPackRoots = opts.discovery.rootsScanned.filter((root) => root.root === "user").map((root) => root.rootPath);
        return ok({
            tool: "bgs_kb_status",
            summary: summary(packs.length, totalRecordCount, warnings.length),
            data: {
                packs,
                cacheRoot,
                userPackRoots,
                totalRecordCount,
                schemaVersionSupported: opts.discovery.supportedSchemaVersion,
            },
            warnings,
            status: "completed",
        });
    };
}
//# sourceMappingURL=status.js.map