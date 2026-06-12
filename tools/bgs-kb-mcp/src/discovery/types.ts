import type { PackManifest } from "../build/types.js";

export type PackRoot = "bundled" | "cache" | "user";

export interface LoadedPack {
  packId: string;
  displayName: string;
  version: string;
  schemaVersion: number;
  minPluginVersion: string;
  root: PackRoot;
  rootPath: string;
  packRoot: string;
  kbSqlitePath: string;
  manifestPath: string;
  manifest: PackManifest;
  integrityOk: boolean;
  loadedAt: string;
}

export type PackCandidate = LoadedPack;

export type SkipReason =
  | { code: "missing_manifest"; path: string; hint: string }
  | { code: "invalid_manifest_json"; path: string; hint: string }
  | { code: "schema_version_unsupported"; path: string; packId?: string; packSchemaVersion: number; supportedSchemaVersion: number }
  | { code: "min_plugin_version_unmet"; path: string; packId?: string; required: string; current: string }
  | { code: "pack_integrity_failed"; path: string; packId?: string; expectedSha256: string; actualSha256: string }
  | { code: "missing_kb_sqlite"; path: string; packId?: string };

export type CollisionReport =
  | {
      code: "pack_id_collision";
      packId: string;
      paths: { root: PackRoot; packRoot: string; builtAt?: string }[];
      hint: string;
    }
  | {
      code: "pack_id_overridden";
      severity: "MEDIUM";
      packId: string;
      winner: { root: PackRoot; packRoot: string; builtAt?: string };
      loser: { root: PackRoot; packRoot: string; builtAt?: string };
      message: string;
    };

export interface DiscoveryResult {
  /** All valid candidates seen before packId precedence is applied. */
  candidates: PackCandidate[];
  packs: LoadedPack[];
  skipped: SkipReason[];
  collisions: CollisionReport[];
  rootsScanned: { root: PackRoot; rootPath: string; existed: boolean }[];
  supportedSchemaVersion: number;
  currentPluginVersion: string;
}

export interface DiscoveryOptions {
  bundledRoot?: string;
  cacheRoot?: string;
  userPackRoots?: string[];
  supportedSchemaVersion?: number;
  currentPluginVersion?: string;
  verifyIntegrity?: boolean;
  now?: () => Date;
}
