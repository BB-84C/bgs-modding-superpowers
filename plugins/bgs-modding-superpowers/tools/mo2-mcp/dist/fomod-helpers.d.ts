/**
 * fomod-helpers — shared FOMOD detection + choices-shape helpers used by
 * mo2_install (initial install) and mo2_reinstall_mod (reinstall via Pattern A).
 *
 * These centralize the contract between the TS MCP layer and the sidecar's
 * `fomod.parse_choices` / `install.stage_fomod` handlers so the two callers
 * cannot drift apart. In particular, the `not_a_fomod` / `info.xml` error
 * substring is the sidecar's documented signal that an archive contains no
 * FOMOD installer; treating that exception as `isFomod=false` (instead of
 * propagating it) is the contract.
 *
 * Refactored 2026-06-17 v1.2 Batch 4 Lane 4C (BUG-22 + BUG-23 + BUG-24): before
 * this file existed, `mo2_install` and `mo2_reinstall_mod` each carried their
 * own copy of the detection regex with subtly different shapes (install
 * returned the tree on success; reinstall returned only a boolean). Drift here
 * was the root cause of BUG-24 (reinstall couldn't surface the FOMOD tree at
 * plan time).
 */
/**
 * Minimum shape we need from the sidecar client. Matches both the real
 * SidecarClient (sidecar-client.ts) and the `{ call }` mocks used in tests.
 * Kept structural so we don't drag in the concrete class.
 */
interface SidecarLike {
    call(method: string, params: unknown): Promise<unknown>;
}
export interface FomodDetection {
    /** True when the sidecar successfully parsed a FOMOD installer from the archive. */
    isFomod: boolean;
    /** Parsed FOMOD tree (pages/groups/options) when isFomod=true; null otherwise. */
    tree: unknown | null;
}
/**
 * Detect whether an archive contains a FOMOD installer by asking the sidecar
 * to parse its `fomod/ModuleConfig.xml`.
 *
 * Returns `{ isFomod: true, tree }` on successful parse. Returns
 * `{ isFomod: false, tree: null }` when the sidecar explicitly reports
 * `not_a_fomod` / missing `info.xml`. Re-throws any other error (corrupt
 * archive, sidecar disconnect, pyfomod unavailable, etc.) so callers can
 * surface real failures.
 */
export declare function detectFomod(sidecar: SidecarLike, archivePath: string): Promise<FomodDetection>;
/**
 * Returns true when the caller supplied a non-empty `fomod_choices` array.
 *
 * BUG-19 fix (2026-06-17): explicit empty array `[]` is treated as "no choices"
 * — same as `undefined`. This lets the agent pass `fomod_choices: []` on a
 * non-FOMOD archive without accidentally triggering the FOMOD staging path.
 */
export declare function hasFomodChoices(args: Record<string, unknown>): boolean;
export {};
