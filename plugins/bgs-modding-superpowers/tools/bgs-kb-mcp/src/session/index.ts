import type { LoadedPack } from "../discovery/types.js";
import { openReadOnly, type DatabaseHandle } from "./sqlite-loader.js";
import type { PackSession, SessionRegistry } from "./types.js";

class PackSessionImpl implements PackSession {
  private db: DatabaseHandle | null;
  private prepared = new Map<string, ReturnType<DatabaseHandle["prepare"]>>();

  constructor(public readonly pack: LoadedPack) {
    this.db = openReadOnly(pack.kbSqlitePath);
  }

  private getStmt(sql: string): ReturnType<DatabaseHandle["prepare"]> {
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

  all<T = unknown>(sql: string, params: ReadonlyArray<unknown> = []): T[] {
    return this.getStmt(sql).all<T>(...params);
  }

  get<T = unknown>(sql: string, params: ReadonlyArray<unknown> = []): T | null {
    const row = this.getStmt(sql).get<T>(...params);
    return row === undefined ? null : row;
  }

  close(): void {
    if (this.db === null) return;
    this.prepared.clear();
    try {
      this.db.close();
    } finally {
      this.db = null;
    }
  }
}

export function openSessions(packs: ReadonlyArray<LoadedPack>): SessionRegistry {
  const ordered: PackSession[] = packs.map((pack) => new PackSessionImpl(pack));
  const byId = new Map<string, PackSession>(ordered.map((session) => [session.pack.packId, session]));

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
      for (const session of ordered) fn(session);
    },
    closeAll() {
      for (const session of ordered) {
        try {
          session.close();
        } catch {
          // Best effort: one bad close must not block the remaining sessions.
        }
      }
    },
  };
}

export type { PackSession, SessionRegistry } from "./types.js";
