import type { LoadedPack } from "../discovery/types.js";

/**
 * One opened pack's runtime handle. Survives for the MCP server's lifetime
 * (or until packs are reloaded). Read-only.
 */
export interface PackSession {
  pack: LoadedPack;
  /**
   * Run a SELECT and return all rows. Throws on bind/exec error.
   * The caller is responsible for SQL shape; the param array is bound by
   * positional ? markers.
   */
  all<T = unknown>(sql: string, params?: ReadonlyArray<unknown>): T[];
  /**
   * Run a SELECT and return the first row, or null if no rows.
   */
  get<T = unknown>(sql: string, params?: ReadonlyArray<unknown>): T | null;
  /**
   * Close this pack's connection. Idempotent; safe to call multiple times.
   */
  close(): void;
}

/**
 * The MCP server's view over all loaded packs. Maps packId -> PackSession.
 * Provides a `forEach` / `byPackId` / `closeAll` surface so consumers
 * (bgs_kb_status, bgs_kb_query, bgs_kb_get) can iterate without touching
 * the underlying Map directly.
 */
export interface SessionRegistry {
  /** Number of currently open pack sessions. */
  size: number;
  /** Look up a single pack session by packId. Returns null if not loaded. */
  byPackId(packId: string): PackSession | null;
  /** All loaded sessions in discovery-priority order (bundled, then cache, then user). */
  all(): PackSession[];
  /** Iterator helper for query fan-out: callback receives each session in priority order. */
  forEach(fn: (session: PackSession) => void): void;
  /** Close every session. Idempotent. */
  closeAll(): void;
}
