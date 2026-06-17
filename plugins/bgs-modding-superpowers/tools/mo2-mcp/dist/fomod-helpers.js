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
export async function detectFomod(sidecar, archivePath) {
    try {
        const tree = await sidecar.call("fomod.parse_choices", { archive_path: archivePath });
        return { isFomod: true, tree };
    }
    catch (e) {
        if (e instanceof Error && /not_a_fomod|info\.xml/i.test(e.message)) {
            return { isFomod: false, tree: null };
        }
        throw e;
    }
}
/**
 * Returns true when the caller supplied a non-empty `fomod_choices` array.
 *
 * BUG-19 fix (2026-06-17): explicit empty array `[]` is treated as "no choices"
 * — same as `undefined`. This lets the agent pass `fomod_choices: []` on a
 * non-FOMOD archive without accidentally triggering the FOMOD staging path.
 */
export function hasFomodChoices(args) {
    return Array.isArray(args.fomod_choices) && args.fomod_choices.length > 0;
}
