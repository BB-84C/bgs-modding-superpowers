/**
 * Detect whether an archive contains a FOMOD installer by asking the sidecar
 * to parse its `fomod/ModuleConfig.xml`.
 *
 * Returns `{ isFomod: true, tree }` on successful parse. Returns
 * `{ isFomod: false, tree: null }` when the sidecar explicitly reports
 * `not_a_fomod` / missing `info.xml`. Re-throws any other error (corrupt
 * archive, sidecar disconnect, pyfomod unavailable, etc.) so callers can
 * surface real failures.
 *
 * Lane V3 FOMOD-EXT (2026-06-17): `mo2State` is an optional object forwarded
 * to the sidecar so pyfomod can evaluate `<moduleDependencies>`,
 * `<visible>` page conditions, and `<dependencyType>` option conditions
 * against current MO2 state. When supplied, the returned `tree` carries
 * `module_dependencies_status`, per-page `dependencies_status`, and per-option
 * `dependencies_status` fields (see FomodTreeShape). The mo2State shape is
 * deliberately structural (Record<string, unknown>) so this helper stays
 * coupled only to the sidecar JSON contract — see mo2-state-for-fomod.ts for
 * the gatherer that produces the real shape.
 */
export async function detectFomod(sidecar, archivePath, mo2State) {
    try {
        const params = { archive_path: archivePath };
        if (mo2State !== undefined && mo2State !== null) {
            params.mo2_state = mo2State;
        }
        const tree = await sidecar.call("fomod.parse_choices", params);
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
