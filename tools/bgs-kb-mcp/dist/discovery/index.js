import { existsSync } from "node:fs";
import { readdir, readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { defaultCacheRoot, parseUserPackRoots, resolvePluginRoot } from "./resolve-roots.js";
import { sha256File } from "./sha256.js";
const ROOT_PRECEDENCE = {
    bundled: 3,
    cache: 2,
    user: 1,
};
function parseSemver(version) {
    if (!version)
        return [0, 0, 0];
    const parts = version.split(".");
    if (parts.length > 3)
        return [0, 0, 0];
    const parsed = parts.map((part) => {
        if (!/^\d+$/.test(part))
            return Number.NaN;
        return Number(part);
    });
    if (parsed.some((part) => Number.isNaN(part)))
        return [0, 0, 0];
    return [parsed[0] ?? 0, parsed[1] ?? 0, parsed[2] ?? 0];
}
function compareSemver(a, b) {
    const left = parseSemver(a);
    const right = parseSemver(b);
    for (let i = 0; i < 3; i += 1) {
        if (left[i] !== right[i])
            return left[i] - right[i];
    }
    return 0;
}
async function readCurrentPluginVersion(pluginRoot) {
    try {
        const parsed = JSON.parse(await readFile(join(pluginRoot, "package.json"), "utf8"));
        return typeof parsed.version === "string" ? parsed.version : "0.1.0";
    }
    catch {
        return "0.1.0";
    }
}
async function listPackDirectories(rootPath) {
    const entries = await readdir(rootPath, { withFileTypes: true });
    return entries
        .filter((entry) => entry.isDirectory())
        .map((entry) => join(rootPath, entry.name))
        .sort((a, b) => a.localeCompare(b));
}
async function readManifest(manifestPath) {
    return JSON.parse(await readFile(manifestPath, "utf8"));
}
async function scanCandidate(args) {
    const manifestPath = join(args.packRoot, "manifest.json");
    const kbSqlitePath = join(args.packRoot, "kb.sqlite");
    if (!existsSync(manifestPath)) {
        return { skipped: { code: "missing_manifest", path: args.packRoot, hint: "Candidate pack directory is missing manifest.json." } };
    }
    let manifest;
    try {
        manifest = await readManifest(manifestPath);
    }
    catch (error) {
        return { skipped: { code: "invalid_manifest_json", path: args.packRoot, hint: error instanceof Error ? error.message : String(error) } };
    }
    if (manifest.schemaVersion > args.supportedSchemaVersion) {
        return {
            skipped: {
                code: "schema_version_unsupported",
                path: args.packRoot,
                packId: manifest.packId,
                packSchemaVersion: manifest.schemaVersion,
                supportedSchemaVersion: args.supportedSchemaVersion,
            },
        };
    }
    if (compareSemver(manifest.minPluginVersion, args.currentPluginVersion) > 0) {
        return {
            skipped: {
                code: "min_plugin_version_unmet",
                path: args.packRoot,
                packId: manifest.packId,
                required: manifest.minPluginVersion,
                current: args.currentPluginVersion,
            },
        };
    }
    if (!existsSync(kbSqlitePath)) {
        return { skipped: { code: "missing_kb_sqlite", path: args.packRoot, packId: manifest.packId } };
    }
    let integrityOk = true;
    if (args.verifyIntegrity) {
        const actualSha256 = await sha256File(kbSqlitePath);
        const expectedSha256 = manifest.sha256["kb.sqlite"];
        integrityOk = actualSha256 === expectedSha256;
        if (!integrityOk) {
            return {
                skipped: {
                    code: "pack_integrity_failed",
                    path: args.packRoot,
                    packId: manifest.packId,
                    expectedSha256,
                    actualSha256,
                },
            };
        }
    }
    return {
        pack: {
            packId: manifest.packId,
            displayName: manifest.displayName,
            version: manifest.version,
            schemaVersion: manifest.schemaVersion,
            minPluginVersion: manifest.minPluginVersion,
            root: args.root,
            rootPath: args.rootPath,
            packRoot: args.packRoot,
            kbSqlitePath,
            manifestPath,
            manifest,
            integrityOk,
            loadedAt: args.loadedAt,
        },
    };
}
function builtAt(pack) {
    const value = pack.manifest.builtAt;
    return typeof value === "string" && value.length > 0 ? value : undefined;
}
function builtAtTime(pack) {
    const value = builtAt(pack);
    if (!value)
        return undefined;
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? undefined : parsed;
}
function compareCandidatesByPrecedence(a, b) {
    const aTime = builtAtTime(a);
    const bTime = builtAtTime(b);
    if (aTime !== undefined && bTime !== undefined && aTime !== bTime)
        return bTime - aTime;
    if (aTime !== undefined && bTime === undefined)
        return -1;
    if (aTime === undefined && bTime !== undefined)
        return 1;
    const rootDelta = ROOT_PRECEDENCE[b.root] - ROOT_PRECEDENCE[a.root];
    if (rootDelta !== 0)
        return rootDelta;
    return a.packRoot.localeCompare(b.packRoot);
}
export function selectWinner(candidates) {
    if (candidates.length === 0)
        throw new Error("selectWinner requires at least one candidate");
    const ordered = [...candidates].sort(compareCandidatesByPrecedence);
    return { winner: ordered[0], losers: ordered.slice(1) };
}
function packRef(pack) {
    return { root: pack.root, packRoot: pack.packRoot, builtAt: builtAt(pack) };
}
function builtAtLabel(pack) {
    return builtAt(pack) ?? "<missing>";
}
function overrideWarning(packId, winner, loser) {
    return {
        code: "pack_id_overridden",
        severity: "MEDIUM",
        packId,
        winner: packRef(winner),
        loser: packRef(loser),
        message: `Pack id ${packId}: ${winner.root}:${winner.packRoot} wins (builtAt ${builtAtLabel(winner)}); overridden: ${loser.root}:${loser.packRoot} (builtAt ${builtAtLabel(loser)})`,
    };
}
function legacyCollision(packId, group) {
    return {
        code: "pack_id_collision",
        packId,
        paths: group.map((pack) => packRef(pack)),
        hint: "Precedence sorter could not pick a deterministic winner; remove or rename duplicate packs so each packId is unique across discovery roots.",
    };
}
export function applyPrecedence(candidates) {
    const groups = new Map();
    for (const candidate of candidates) {
        const group = groups.get(candidate.packId) ?? [];
        group.push(candidate);
        groups.set(candidate.packId, group);
    }
    const packs = [];
    const collisions = [];
    for (const [packId, group] of groups) {
        if (group.length === 1) {
            packs.push(group[0]);
            continue;
        }
        try {
            const { winner, losers } = selectWinner(group);
            packs.push(winner);
            for (const loser of losers)
                collisions.push(overrideWarning(packId, winner, loser));
        }
        catch {
            collisions.push(legacyCollision(packId, group));
        }
    }
    return { packs, collisions };
}
export async function discoverPacks(opts = {}) {
    const pluginRoot = resolvePluginRoot(import.meta.url);
    const bundledRoot = resolve(opts.bundledRoot ?? join(pluginRoot, "knowledge", "bgs-kb", "packs"));
    const cacheRoot = resolve(opts.cacheRoot ?? defaultCacheRoot());
    const userPackRoots = (opts.userPackRoots ?? parseUserPackRoots(process.env.BGS_KB_USER_PACKS)).map((root) => resolve(root));
    const supportedSchemaVersion = opts.supportedSchemaVersion ?? 1;
    // currentPluginVersion: explicit opt wins; otherwise read from <plugin-root>/package.json.
    // On read failure, readCurrentPluginVersion falls back to "0.1.0" (the initial version).
    // The minPluginVersion gate in each pack is the real compat surface — no flooring here.
    const currentPluginVersion = opts.currentPluginVersion ?? (await readCurrentPluginVersion(pluginRoot));
    const verifyIntegrity = opts.verifyIntegrity ?? true;
    const loadedAt = (opts.now ?? (() => new Date()))().toISOString();
    const roots = [
        { root: "bundled", rootPath: bundledRoot },
        { root: "cache", rootPath: cacheRoot },
        ...userPackRoots.map((rootPath) => ({ root: "user", rootPath })),
    ];
    const rootsScanned = [];
    const skipped = [];
    const candidates = [];
    for (const root of roots) {
        const existed = existsSync(root.rootPath);
        rootsScanned.push({ ...root, existed });
        if (!existed)
            continue;
        for (const packRoot of await listPackDirectories(root.rootPath)) {
            const result = await scanCandidate({
                ...root,
                packRoot,
                supportedSchemaVersion,
                currentPluginVersion,
                verifyIntegrity,
                loadedAt,
            });
            if (result.skipped)
                skipped.push(result.skipped);
            if (result.pack)
                candidates.push(result.pack);
        }
    }
    const { packs, collisions } = applyPrecedence(candidates);
    return {
        candidates,
        packs,
        skipped,
        collisions,
        rootsScanned,
        supportedSchemaVersion,
        currentPluginVersion,
    };
}
//# sourceMappingURL=index.js.map