/**
 * fomod-mo2-state — Lane V3 FOMOD-EXT phase 4 tests.
 *
 * Covers:
 *   - gatherMo2FomodState reads enabled plugins from plugins.txt
 *   - gatherMo2FomodState gracefully tolerates missing profile dir
 *   - detectFomod forwards mo2State to the sidecar's fomod.parse_choices call
 *   - FomodTreeShape accepts the new dependencies_status / conditional_pages_note
 *     fields (compile-time + structural assertion)
 *
 * Uses tmpdir fixtures + mocked sidecar — no real MO2 / pyfomod involvement.
 */
import { describe, it, expect } from "vitest";
import { mkdtempSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { gatherMo2FomodState } from "../src/mo2-state-for-fomod.js";
import { detectFomod } from "../src/fomod-helpers.js";
import type { FomodTreeShape, FomodDependencyStatus } from "../src/fomod-required-error.js";
import type { ToolContext } from "../src/types.js";
import type { Config } from "../src/config.js";

function makeMo2Tmpdir(): string {
  const root = mkdtempSync(join(tmpdir(), "mo2-fomod-state-"));
  // minimal ModOrganizer.ini
  writeFileSync(
    join(root, "ModOrganizer.ini"),
    "[General]\ngameName=Fallout4\n[Settings]\nmodDirectory=\n",
    "utf8",
  );
  // profile dir with plugins.txt + modlist.txt
  const profileDir = join(root, "profiles", "Default");
  mkdirSync(profileDir, { recursive: true });
  writeFileSync(
    join(profileDir, "plugins.txt"),
    "# header comment\n*Fallout4.esm\n*DLCCoast.esm\nDisabledMod.esp\n*CBBE.esp\n",
    "utf8",
  );
  writeFileSync(
    join(profileDir, "modlist.txt"),
    "+ModA\n-ModB\n+ModC\n",
    "utf8",
  );
  return root;
}

function makeCtx(mo2Root: string): ToolContext {
  // Use the legacy fixture path (`ctx.config` without `ctx.binding`) — see
  // binding.ts requireBoundContext. This is the same shape that
  // fomod-required-error.test.ts uses.
  return {
    config: {
      mo2Root,
      permissionCeiling: "metadata-editable",
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: join(mo2Root, ".mo2-mcp", "snapshots"),
      auditRoot: join(mo2Root, ".mo2-mcp", "audit"),
    } as Config,
    sessionId: "fomod-mo2-state-test",
  } as unknown as ToolContext;
}

describe("gatherMo2FomodState", () => {
  it("reads enabled plugins (* prefix), drops the disabled ones, and the comment header", async () => {
    const root = makeMo2Tmpdir();
    try {
      const ctx = makeCtx(root);
      const state = await gatherMo2FomodState(ctx, "Default");
      // Only * lines that are not comments
      expect(state.enabled_plugins).toEqual([
        "Fallout4.esm",
        "DLCCoast.esm",
        "CBBE.esp",
      ]);
      // No gameVersion key in the ini -> null
      expect(state.game_version).toBeNull();
      // Phase-bounded scope: provided_files empty by design (v1.3 doesn't walk mod dirs)
      expect(state.provided_files).toEqual([]);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it("returns an empty plugin list when the profile dir is missing", async () => {
    const root = mkdtempSync(join(tmpdir(), "mo2-fomod-state-noprof-"));
    try {
      writeFileSync(
        join(root, "ModOrganizer.ini"),
        "[General]\ngameName=Fallout4\n[Settings]\nmodDirectory=\n",
        "utf8",
      );
      // Note: no profiles/<name>/ dir at all
      const ctx = makeCtx(root);
      const state = await gatherMo2FomodState(ctx, "Default");
      expect(state.enabled_plugins).toEqual([]);
      expect(state.game_version).toBeNull();
      expect(state.provided_files).toEqual([]);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it("returns an empty state when ModOrganizer.ini is missing", async () => {
    const root = mkdtempSync(join(tmpdir(), "mo2-fomod-state-noini-"));
    try {
      const profileDir = join(root, "profiles", "Default");
      mkdirSync(profileDir, { recursive: true });
      writeFileSync(join(profileDir, "plugins.txt"), "*OnlyOne.esp\n", "utf8");
      writeFileSync(join(profileDir, "modlist.txt"), "+x\n", "utf8");
      const ctx = makeCtx(root);
      // Even though the INI is missing, profile plugins still get read.
      const state = await gatherMo2FomodState(ctx, "Default");
      expect(state.enabled_plugins).toEqual(["OnlyOne.esp"]);
      expect(state.game_version).toBeNull();
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});

describe("detectFomod forwards mo2State to the sidecar", () => {
  it("passes mo2_state through to fomod.parse_choices when supplied", async () => {
    const seenParams: unknown[] = [];
    const sidecar = {
      async call(method: string, params: unknown): Promise<unknown> {
        seenParams.push({ method, params });
        return {
          fomod_name: "Test",
          fomod_version: "1.0",
          conditional_pages_note: null,
          pages: [],
          module_dependencies_status: { met: true, missing: [] },
        };
      },
    };
    const result = await detectFomod(sidecar, "C:/some/archive.7z", {
      enabled_plugins: ["CBBE.esp"],
      game_version: "1.10.163.0",
      provided_files: [],
    });
    expect(result.isFomod).toBe(true);
    expect(seenParams).toHaveLength(1);
    const call = seenParams[0] as { method: string; params: Record<string, unknown> };
    expect(call.method).toBe("fomod.parse_choices");
    expect(call.params.archive_path).toBe("C:/some/archive.7z");
    expect(call.params.mo2_state).toEqual({
      enabled_plugins: ["CBBE.esp"],
      game_version: "1.10.163.0",
      provided_files: [],
    });
  });

  it("omits mo2_state from the params when not supplied (back-compat with v1.2 sidecar)", async () => {
    const seenParams: unknown[] = [];
    const sidecar = {
      async call(method: string, params: unknown): Promise<unknown> {
        seenParams.push({ method, params });
        return { fomod_name: "Test", fomod_version: null, conditional_pages_note: null, pages: [] };
      },
    };
    await detectFomod(sidecar, "C:/some/archive.7z");
    const call = seenParams[0] as { params: Record<string, unknown> };
    expect("mo2_state" in call.params).toBe(false);
  });

  it("still returns isFomod=false when sidecar raises not_a_fomod (back-compat preserved)", async () => {
    const sidecar = {
      async call(): Promise<unknown> {
        throw new Error("not_a_fomod: missing info.xml");
      },
    };
    const result = await detectFomod(sidecar, "C:/plain.zip", {
      enabled_plugins: ["X.esp"],
      game_version: null,
      provided_files: [],
    });
    expect(result.isFomod).toBe(false);
    expect(result.tree).toBeNull();
  });

  it("re-throws non-not_a_fomod errors unchanged", async () => {
    const sidecar = {
      async call(): Promise<unknown> {
        throw new Error("pyfomod_not_available");
      },
    };
    await expect(
      detectFomod(sidecar, "C:/x.7z", { enabled_plugins: [], game_version: null, provided_files: [] }),
    ).rejects.toThrow("pyfomod_not_available");
  });
});

describe("FomodTreeShape accepts the V3 dependency-status fields", () => {
  it("compiles + structurally validates a tree with all V3 fields populated", () => {
    // This is primarily a TypeScript compile-time test (the shape change in
    // fomod-required-error.ts must accept these fields). The runtime
    // assertions confirm the parser/agent contract round-trips through the
    // interface without losing structure.
    const status: FomodDependencyStatus = { met: false, missing: ["file CBBE.esp must be Active (was Missing)"] };
    const tree: FomodTreeShape = {
      fomod_name: "CBBEPatch",
      fomod_version: "2.0",
      conditional_pages_note: "This FOMOD declares conditional pages...",
      module_dependencies_status: { met: true, missing: [] },
      pages: [
        {
          name: "Main",
          dependencies_status: { met: true, missing: [] },
          groups: [
            {
              name: "Variant",
              type: "SelectExactlyOne",
              options: [
                {
                  name: "CBBE Patch",
                  description: "Requires CBBE",
                  image: null,
                  type: "NotUsable",
                  dependencies_status: status,
                },
              ],
            },
          ],
        },
      ],
    };
    expect(tree.module_dependencies_status?.met).toBe(true);
    expect(tree.conditional_pages_note).toContain("conditional");
    expect(tree.pages[0].dependencies_status?.met).toBe(true);
    const opt = tree.pages[0].groups[0].options[0];
    expect(opt.type).toBe("NotUsable");
    expect(opt.dependencies_status?.met).toBe(false);
    expect(opt.dependencies_status?.missing[0]).toContain("CBBE.esp");
  });

  it("accepts a tree without V3 fields (back-compat with v1.2 sidecar)", () => {
    const tree: FomodTreeShape = {
      fomod_name: "Plain",
      fomod_version: null,
      pages: [
        {
          name: "OnlyStep",
          groups: [
            {
              name: "g",
              type: "SelectAny",
              options: [
                { name: "o", description: "d", image: null, type: "Optional" },
              ],
            },
          ],
        },
      ],
    };
    expect(tree.module_dependencies_status).toBeUndefined();
    expect(tree.conditional_pages_note).toBeUndefined();
    expect(tree.pages[0].dependencies_status).toBeUndefined();
    expect(tree.pages[0].groups[0].options[0].dependencies_status).toBeUndefined();
  });
});
