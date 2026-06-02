import { openReadOnly } from "./sqlite-loader.js";
class PackSessionImpl {
    pack;
    db;
    prepared = new Map();
    constructor(pack) {
        this.pack = pack;
        this.db = openReadOnly(pack.kbSqlitePath);
    }
    getStmt(sql) {
        if (this.db === null) {
            throw new Error(`PackSession for ${this.pack.packId} is closed`);
        }
        let stmt = this.prepared.get(sql);
        if (!stmt) {
            stmt = this.db.prepare(sql);
            this.prepared.set(sql, stmt);
        }
        return stmt;
    }
    all(sql, params = []) {
        return this.getStmt(sql).all(...params);
    }
    get(sql, params = []) {
        const row = this.getStmt(sql).get(...params);
        return row === undefined ? null : row;
    }
    close() {
        if (this.db === null)
            return;
        this.prepared.clear();
        try {
            this.db.close();
        }
        finally {
            this.db = null;
        }
    }
}
export function openSessions(packs) {
    const ordered = packs.map((pack) => new PackSessionImpl(pack));
    const byId = new Map(ordered.map((session) => [session.pack.packId, session]));
    return {
        get size() {
            return ordered.length;
        },
        byPackId(packId) {
            return byId.get(packId) ?? null;
        },
        all() {
            return ordered.slice();
        },
        forEach(fn) {
            for (const session of ordered)
                fn(session);
        },
        closeAll() {
            for (const session of ordered) {
                try {
                    session.close();
                }
                catch {
                    // Best effort: one bad close must not block the remaining sessions.
                }
            }
        },
    };
}
//# sourceMappingURL=index.js.map