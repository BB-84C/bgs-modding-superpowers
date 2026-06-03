import { rm } from "node:fs/promises";
import { resolve, join } from "node:path";
import { buildManifest, readPackMeta, sha256File, writeManifest } from "./manifest.js";
import { readRecords } from "./read-records.js";
import { applySchema, insertRecord, openDb, writePackMeta } from "./sqlite.js";
import { validateRecords } from "./validate.js";
export class BuildValidationError extends Error {
    validationErrors;
    constructor(validationErrors) {
        super(`Build validation failed for ${validationErrors.length} record(s)`);
        this.validationErrors = validationErrors;
        this.name = "BuildValidationError";
    }
}
export async function buildPack(packRoot) {
    const resolvedPackRoot = resolve(packRoot);
    const records = await readRecords(resolvedPackRoot);
    const validation = validateRecords(records, resolvedPackRoot);
    if (validation.errors.length > 0) {
        throw new BuildValidationError(validation.errors);
    }
    const builtAt = new Date().toISOString();
    const meta = await readPackMeta(resolvedPackRoot);
    const kbSqlitePath = join(resolvedPackRoot, "kb.sqlite");
    await rm(kbSqlitePath, { force: true });
    const db = openDb(kbSqlitePath);
    try {
        applySchema(db);
        writePackMeta(db, meta, validation.valid.length, builtAt);
        for (const record of validation.valid)
            insertRecord(db, record, meta.packId);
    }
    finally {
        db.close();
    }
    const sha256 = await sha256File(kbSqlitePath);
    const manifest = await buildManifest({ packRoot: resolvedPackRoot, records: validation.valid, meta, builtAt, sha256 });
    const manifestPath = await writeManifest(resolvedPackRoot, manifest);
    return {
        packRoot: resolvedPackRoot,
        recordCount: validation.valid.length,
        kbSqlitePath,
        manifestPath,
        sha256,
        builtAt,
        manifest,
    };
}
//# sourceMappingURL=index.js.map