import { existsSync } from "node:fs";
import { mkdir, readFile, rename, rm } from "node:fs/promises";
import { dirname, join } from "node:path";
import { z } from "zod";
import { ok, refuse } from "../envelope/index.js";
import { KB_ERROR_CODES } from "../envelope/types.js";
import { fetchReleaseIndex } from "./updates/release-index.js";
import { compareVersions } from "./updates/semver.js";
import { resolveInstallCachePaths } from "./install/cache-paths.js";
import { downloadToFile, DownloadFailure, IntegrityFailure } from "./install/download.js";
import { extractZip } from "./install/extract.js";
const Args = z.object({ packId: z.string().min(1), version: z.string().min(1).refine((value) => value !== "latest", "version must be exact; 'latest' is not allowed"), dryRun: z.boolean().optional() }).strict();
async function readExtractedManifest(extractPath) {
    return JSON.parse(await readFile(join(extractPath, "manifest.json"), "utf8"));
}
export function makeInstallPackTool(opts) {
    return async (rawArgs) => {
        const parsed = Args.safeParse(rawArgs);
        if (!parsed.success) {
            return refuse({
                tool: "bgs_kb_install_pack",
                summary: "Invalid bgs_kb_install_pack request",
                code: KB_ERROR_CODES.INVALID_REQUEST,
                hint: "Call bgs_kb_install_pack with { packId, version, dryRun? }; version must be an exact version string.",
                detail: { issues: parsed.error.issues },
                severity: "MEDIUM",
            });
        }
        const { packId, version, dryRun = false } = parsed.data;
        const paths = resolveInstallCachePaths(opts.cacheRoot, packId, version, opts.tempId?.());
        try {
            const index = await (opts.releaseIndexFetcher ?? (() => fetchReleaseIndex()))();
            const entry = index.packs.find((candidate) => candidate.packId === packId && candidate.version === version);
            if (!entry) {
                return refuse({
                    tool: "bgs_kb_install_pack",
                    summary: `No release asset found for ${packId}@${version}`,
                    code: KB_ERROR_CODES.DOWNLOAD_FAILED,
                    hint: "Run bgs_kb_check_updates first and pass an exact available version.",
                    severity: "MEDIUM",
                });
            }
            if (existsSync(paths.targetPath) && !dryRun) {
                return refuse({
                    tool: "bgs_kb_install_pack",
                    summary: `${packId}@${version} is already installed`,
                    code: KB_ERROR_CODES.DOWNLOAD_FAILED,
                    hint: `Target path already exists: ${paths.targetPath}`,
                    severity: "MEDIUM",
                });
            }
            const download = await downloadToFile({ url: entry.releaseUrl, destPath: paths.zipPath, expectedSha256: entry.sha256, expectedSizeBytes: entry.sizeBytes, fetchImpl: opts.fetchImpl });
            await (opts.extractZipImpl ?? extractZip)(paths.zipPath, paths.extractPath);
            const manifest = await readExtractedManifest(paths.extractPath);
            if (manifest.schemaVersion > opts.supportedSchemaVersion) {
                return refuse({
                    tool: "bgs_kb_install_pack",
                    summary: `${packId}@${version} requires schemaVersion ${manifest.schemaVersion}`,
                    code: KB_ERROR_CODES.SCHEMA_VERSION_UNSUPPORTED,
                    hint: `This MCP supports schemaVersion ${opts.supportedSchemaVersion}.`,
                    severity: "HIGH",
                });
            }
            if (compareVersions(manifest.minPluginVersion, opts.currentPluginVersion) > 0) {
                return refuse({
                    tool: "bgs_kb_install_pack",
                    summary: `${packId}@${version} requires plugin >= ${manifest.minPluginVersion}`,
                    code: KB_ERROR_CODES.MIN_PLUGIN_VERSION_UNMET,
                    hint: `Current plugin version is ${opts.currentPluginVersion}.`,
                    severity: "HIGH",
                });
            }
            if (!dryRun) {
                await mkdir(dirname(paths.targetPath), { recursive: true });
                await rename(paths.extractPath, paths.targetPath);
            }
            return ok({
                tool: "bgs_kb_install_pack",
                summary: dryRun ? `Verified install plan for ${packId}@${version}` : `Installed ${packId}@${version}`,
                data: { installed: { packId, version, path: paths.targetPath }, bytesDownloaded: download.bytesDownloaded, sha256Verified: true, schemaVersionOk: true, minPluginVersionOk: true },
                status: "completed",
            });
        }
        catch (error) {
            if (error instanceof IntegrityFailure) {
                return refuse({
                    tool: "bgs_kb_install_pack",
                    summary: `Downloaded ${packId}@${version} failed sha256 verification`,
                    code: KB_ERROR_CODES.PACK_INTEGRITY_FAILED,
                    hint: error.message,
                    detail: { expectedSha256: error.expectedSha256, actualSha256: error.actualSha256 },
                    severity: "CRITICAL",
                });
            }
            const message = error instanceof Error ? error.message : String(error);
            return refuse({
                tool: "bgs_kb_install_pack",
                summary: `Failed to download or install ${packId}@${version}: ${message}`,
                code: error instanceof DownloadFailure ? KB_ERROR_CODES.DOWNLOAD_FAILED : KB_ERROR_CODES.DOWNLOAD_FAILED,
                hint: message,
                severity: "HIGH",
            });
        }
        finally {
            await rm(paths.zipPath, { force: true }).catch(() => undefined);
            if (dryRun || !existsSync(paths.targetPath))
                await rm(paths.extractPath, { force: true, recursive: true }).catch(() => undefined);
        }
    };
}
//# sourceMappingURL=install-pack.js.map