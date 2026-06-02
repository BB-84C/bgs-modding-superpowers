import { existsSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { basename, join, resolve } from "node:path";
import { sha256File } from "../build/manifest.js";
import { readRecords } from "../build/read-records.js";
const require = createRequire(import.meta.url);
const { DatabaseSync } = require("node:sqlite");
function sortEntries(record) {
    return Object.fromEntries(Object.entries(record).sort(([a], [b]) => a.localeCompare(b)));
}
function countRecords(records, values) {
    const counts = {};
    for (const record of records) {
        for (const value of values(record))
            counts[value] = (counts[value] ?? 0) + 1;
    }
    return sortEntries(counts);
}
function uniqueSorted(records, values) {
    return [...new Set(records.flatMap(values))].sort((a, b) => a.localeCompare(b));
}
function getNumber(row, key) {
    const value = row?.[key];
    return typeof value === "number" ? value : 0;
}
function countRows(rows, key) {
    const counts = {};
    for (const row of rows) {
        const obj = row;
        const name = obj[key];
        const count = obj.n;
        if (typeof name === "string" && typeof count === "number")
            counts[name] = count;
    }
    return sortEntries(counts);
}
async function readManifest(manifestPath) {
    if (!existsSync(manifestPath))
        return undefined;
    return JSON.parse(await readFile(manifestPath, "utf8"));
}
function readSqlite(sqlitePath) {
    const db = new DatabaseSync(sqlitePath, { readOnly: true });
    try {
        const recordCount = getNumber(db.prepare("SELECT COUNT(*) AS n FROM records").get(), "n");
        const byDomain = countRows(db.prepare("SELECT domain, COUNT(*) AS n FROM record_domains GROUP BY domain ORDER BY domain").all(), "domain");
        const byGame = countRows(db.prepare("SELECT game, COUNT(*) AS n FROM record_games GROUP BY game ORDER BY game").all(), "game");
        return { recordCount, byDomain, byGame };
    }
    finally {
        db.close();
    }
}
export async function gatherInfo(packRoot) {
    const resolvedPackRoot = resolve(packRoot);
    const manifestPath = join(resolvedPackRoot, "manifest.json");
    const sqlitePath = join(resolvedPackRoot, "kb.sqlite");
    const warnings = [];
    const records = await readRecords(resolvedPackRoot);
    const manifest = await readManifest(manifestPath);
    if (!manifest) {
        warnings.push("manifest.json missing; pack has not been built yet. Run `bgs-kb-mcp build <pack-root>`.");
    }
    let sqlite;
    let liveByDomain;
    let liveByGame;
    if (!existsSync(sqlitePath)) {
        warnings.push("kb.sqlite missing; counts from manifest only.");
    }
    else {
        const live = readSqlite(sqlitePath);
        const sha256 = await sha256File(sqlitePath);
        const sha256Verified = manifest ? sha256 === manifest.sha256["kb.sqlite"] : undefined;
        if (sha256Verified === false)
            warnings.push("kb.sqlite sha256 does NOT match manifest. Rebuild recommended.");
        if (manifest && live.recordCount !== manifest.recordCount) {
            warnings.push(`kb.sqlite record count (${live.recordCount}) ≠ manifest recordCount (${manifest.recordCount}).`);
        }
        sqlite = {
            path: sqlitePath,
            sizeBytes: statSync(sqlitePath).size,
            sha256,
            sha256Verified,
            recordCount: live.recordCount,
        };
        liveByDomain = live.byDomain;
        liveByGame = live.byGame;
    }
    const derivedDomains = uniqueSorted(records, (record) => record.domains);
    const derivedGames = uniqueSorted(records, (record) => record.appliesTo.games);
    const derivedEngineFamilies = uniqueSorted(records, (record) => record.appliesTo.engineFamilies ?? []);
    return {
        packRoot: resolvedPackRoot,
        manifestPath,
        sqlitePath,
        manifest,
        sqlite,
        warnings,
        derivedRecordCount: records.length,
        domains: manifest?.domains ?? derivedDomains,
        games: manifest?.games ?? derivedGames,
        engineFamilies: manifest?.engineFamilies ?? derivedEngineFamilies,
        byDomain: liveByDomain ?? countRecords(records, (record) => record.domains),
        byGame: liveByGame ?? countRecords(records, (record) => record.appliesTo.games),
    };
}
export function fallbackPackId(info) {
    return info.manifest?.packId ?? basename(info.packRoot);
}
//# sourceMappingURL=index.js.map