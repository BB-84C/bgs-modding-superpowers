import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { AuditLogger } from "../../src/audit.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import type { ToolContext } from "../../src/types.js";

async function setupRoot(opts: {
  profiles?: string[];
  selectedProfile?: string;
  allowedProfiles?: string[];
} = {}): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-status-profile-"));
  for (const profile of opts.profiles ?? []) {
    await mkdir(join(root, "profiles", profile), { recursive: true });
    await writeFile(join(root, "profiles", profile, "modlist.txt"), "+ModA\n-ModB\n", "utf8");
    await writeFile(join(root, "profiles", profile, "plugins.txt"), "*Fallout4.esm\n", "utf8");
  }
  const selectedLine = opts.selectedProfile
    ? `selected_profile=@ByteArray(${opts.selectedProfile})\n`
    : "";
  await writeFile(
    join(root, "ModOrganizer.ini"),
    `[General]\ngame=fallout4\ngameName=Fallout 4\n${selectedLine}[Settings]\nbase_directory=${root}\n`,
    "utf8",
  );

  return {
    root,
    ctx: {
      config: {
        mo2Root: root,
        permissionCeiling: "metadata-editable",
        allowedProfiles: opts.allowedProfiles ?? [],
        deny: [],
        snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
        auditRoot: join(root, ".mo2-mcp", "audit"),
      },
      sessionId: "test",
      plans: new PlanCache(),
      snapshots: new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "test"),
      audit: new AuditLogger(join(root, ".mo2-mcp", "audit"), "test"),
    },
  };
}

async function status(args: Record<string, unknown>, ctx: ToolContext) {
  return await getTool("mo2_status")!.handler(args, ctx) as {
    ok: boolean;
    result?: { profile: string; counts: { mods_total: number } | null };
    error?: { code: string; message: string };
  };
}

describe("mo2_status profile resolution", () => {
  const previousEnvProfile = process.env.BGS_MO2_PROFILE;

  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-status.js");
  });

  beforeEach(() => {
    delete process.env.BGS_MO2_PROFILE;
  });

  afterEach(() => {
    if (previousEnvProfile === undefined) delete process.env.BGS_MO2_PROFILE;
    else process.env.BGS_MO2_PROFILE = previousEnvProfile;
  });

  it("uses args.profile before env, ini, and config fallbacks", async () => {
    process.env.BGS_MO2_PROFILE = "EnvProfile";
    const { ctx } = await setupRoot({
      profiles: ["ArgProfile", "EnvProfile", "IniProfile", "ConfigProfile"],
      selectedProfile: "IniProfile",
      allowedProfiles: ["ConfigProfile"],
    });

    const response = await status({ profile: "ArgProfile" }, ctx);

    expect(response.ok).toBe(true);
    expect(response.result?.profile).toBe("ArgProfile");
    expect(response.result?.counts?.mods_total).toBe(2);
  });

  it("uses BGS_MO2_PROFILE when args.profile is absent", async () => {
    process.env.BGS_MO2_PROFILE = "EnvProfile";
    const { ctx } = await setupRoot({
      profiles: ["EnvProfile", "IniProfile", "ConfigProfile"],
      selectedProfile: "IniProfile",
      allowedProfiles: ["ConfigProfile"],
    });

    const response = await status({}, ctx);

    expect(response.ok).toBe(true);
    expect(response.result?.profile).toBe("EnvProfile");
  });

  it("uses ModOrganizer.ini selected_profile when env is absent", async () => {
    const { ctx } = await setupRoot({
      profiles: ["IniProfile", "ConfigProfile"],
      selectedProfile: "IniProfile",
      allowedProfiles: ["ConfigProfile"],
    });

    const response = await status({}, ctx);

    expect(response.ok).toBe(true);
    expect(response.result?.profile).toBe("IniProfile");
  });

  it("uses config.allowedProfiles[0] when args, env, and ini are absent", async () => {
    const { ctx } = await setupRoot({ profiles: ["ConfigProfile"], allowedProfiles: ["ConfigProfile"] });

    const response = await status({}, ctx);

    expect(response.ok).toBe(true);
    expect(response.result?.profile).toBe("ConfigProfile");
  });

  it("fails clearly when no profile source is available", async () => {
    const { ctx } = await setupRoot();

    const response = await status({}, ctx);

    expect(response.ok).toBe(false);
    expect(response.error?.code).toBe("no_profile_available");
  });

  // BUG-23 (issue #12) Bug 1 regression: real Starfield install with Chinese
  // profile name "BB84自用2" stored as
  //   selected_profile=@ByteArray(BB84\xe8\x87\xaa\xe7\x94\xa8\x32)
  // Earlier deploys (pre 2026-06-24 decodeIniValue \xHH upgrade) returned the
  // literal escaped form, causing readProfile to ENOENT on the wrong path. The
  // decoder upgrade fixed it; this test locks in the end-to-end Status path
  // against the exact byte sequence so the bug class cannot regress silently.
  it("BUG-23 Bug 1: Status resolves Chinese profile name encoded as @ByteArray(\\xHH)", async () => {
    const { ctx } = await setupRoot({
      profiles: ["BB84自用2"],
      // The escaped form @ByteArray(BB84\xe8\x87\xaa\xe7\x94\xa8\x32)
      // decodes via decodeIniValue to "BB84自用2".
      selectedProfile: "BB84\\xe8\\x87\\xaa\\xe7\\x94\\xa8\\x32",
      allowedProfiles: ["Default"],
    });

    const response = await status({}, ctx);

    expect(response.ok).toBe(true);
    expect(response.result?.profile).toBe("BB84自用2");
    expect(response.result?.counts?.mods_total).toBe(2);
    // Critical: the error message in issue #12 contained literal `\xHH`. This
    // assertion proves the resolved profileName is the *decoded* form, not
    // the escaped wire form.
    expect(response.result?.profile).not.toMatch(/\\x[0-9a-fA-F]{2}/);
  });
});
