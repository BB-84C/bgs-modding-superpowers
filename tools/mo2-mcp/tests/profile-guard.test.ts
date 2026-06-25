import { describe, it, expect, beforeEach, afterAll } from "vitest";
import { z } from "zod";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import {
  assertActiveProfile,
  CrossProfileMutationError,
  _resetStaleBrokerWarnedForTests,
} from "../src/profile-guard.js";
import { dispatchToolCall } from "../src/dispatch.js";
import { AuditLogger } from "../src/audit.js";
import { PlanCache } from "../src/plan-apply.js";
import { SnapshotManager } from "../src/snapshot.js";
import { _clearToolsForTests, registerTool } from "../src/tool-registry.js";
import type { ToolContext } from "../src/types.js";
import type { Config } from "../src/config.js";

/**
 * Build a context where the pipe is alive but reports `method_not_found` for
 * `profile.active` (the stale-broker scenario from issue #12). The bound
 * mo2Root points at a temp dir containing a real ModOrganizer.ini whose
 * [General] selected_profile is set to `iniProfile`. This mirrors how the
 * fallback should resolve when the deployed broker is older than the source
 * tree's profile.active handler.
 */
async function ctxWithStaleBrokerAndIni(opts: {
  iniProfile?: string;
  iniProfileByteArray?: boolean;
  /** When set, returns this error code/message instead of method_not_found. */
  brokerError?: { code: string; message: string };
}): Promise<{ ctx: ToolContext; root: string }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-staleb-"));
  if (opts.iniProfile) {
    const profileLine = opts.iniProfileByteArray
      ? `selected_profile=@ByteArray(${opts.iniProfile})`
      : `selected_profile=${opts.iniProfile}`;
    await writeFile(
      join(root, "ModOrganizer.ini"),
      `[General]\ngame=fallout4\ngameName=Fallout4\n${profileLine}\n[Settings]\nbase_directory=${root}\n`,
      "utf8",
    );
  } else {
    await writeFile(
      join(root, "ModOrganizer.ini"),
      `[General]\ngame=fallout4\ngameName=Fallout4\n[Settings]\nbase_directory=${root}\n`,
      "utf8",
    );
  }
  const ctx = {
    config: {
      mo2Root: root,
      allowedProfiles: ["Default"],
      permissionCeiling: "metadata-editable",
      deny: [],
      snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
      auditRoot: join(root, ".mo2-mcp", "audit"),
    },
    pipeClient: {
      call: async () => ({
        ok: false,
        result: null,
        error: opts.brokerError ?? {
          code: "method_not_found",
          message: "Unsupported method: profile.active",
        },
      }),
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    },
  } as unknown as ToolContext;
  return { ctx, root };
}

function ctxWithActiveProfile(activeProfile?: string): ToolContext {
  // Legacy compat shape: ToolContext at runtime carries `binding`, but
  // requireBoundContext also accepts an old-shape ctx with `config` +
  // `pipeClient` for test fixtures that pre-date the lazy-bind refactor.
  // This fixture goes through that compat path.
  return {
    config: { mo2Root: "/test-mo2-root", allowedProfiles: ["Default"], permissionCeiling: "metadata-editable", deny: [], snapshotRoot: "/test-mo2-root/.mo2-mcp/snapshots", auditRoot: "/test-mo2-root/.mo2-mcp/audit" },
    pipeClient: activeProfile === undefined
      ? undefined
      : {
          call: async (method: string) => {
            expect(method).toBe("profile.active");
            return { ok: true, result: { name: activeProfile, path: `profiles/${activeProfile}` }, error: null };
          },
          close: () => {},
          discoverAndConnect: async () => {},
          isConnected: () => true,
        },
  } as unknown as ToolContext;
}

describe("assertActiveProfile", () => {
  it("is a no-op when there is no live pipe", async () => {
    await expect(assertActiveProfile(ctxWithActiveProfile(), "Alt")).resolves.toBeUndefined();
  });

  it("allows live mutation when requested profile matches active profile", async () => {
    await expect(assertActiveProfile(ctxWithActiveProfile("Default"), "Default")).resolves.toBeUndefined();
  });

  it("blocks live mutation when requested profile differs from active profile", async () => {
    await expect(assertActiveProfile(ctxWithActiveProfile("Default"), "BB84自用"))
      .rejects.toThrow(/cross_profile_live_mutation_blocked: requested='BB84自用', active='Default'/);
  });

  // BUG-21 fix (2026-06-17): the cross-profile guard now throws a typed
  // CrossProfileMutationError so dispatch.ts can surface a structured envelope
  // with code='cross_profile_live_mutation_blocked' instead of collapsing it
  // to internal_error.
  // BUG-23 (issue #12) fix (2026-06-25): when the deployed Python broker
  // predates the addition of the `profile.active` handler, the broker returns
  // `{ok: false, error: {code: "method_not_found", ...}}`. assertActiveProfile
  // now treats that specific error as "fall back to ModOrganizer.ini
  // [General] selected_profile" instead of bombing the whole T3 mutator
  // chain. The ini fallback uses the same decodeIniValue path as
  // mo2_modlist, so non-ASCII profile names round-trip correctly.
  describe("BUG-23: stale-broker fallback for profile.active", () => {
    const tempDirs: string[] = [];
    beforeEach(() => {
      _resetStaleBrokerWarnedForTests();
    });
    afterAll(async () => {
      for (const dir of tempDirs) {
        await rm(dir, { recursive: true, force: true }).catch(() => undefined);
      }
    });

    it("falls back to ini selected_profile when broker returns method_not_found (match)", async () => {
      const { ctx, root } = await ctxWithStaleBrokerAndIni({ iniProfile: "Default" });
      tempDirs.push(root);
      await expect(assertActiveProfile(ctx, "Default")).resolves.toBeUndefined();
    });

    it("falls back to ini selected_profile when broker returns method_not_found (mismatch -> CrossProfileMutationError)", async () => {
      const { ctx, root } = await ctxWithStaleBrokerAndIni({ iniProfile: "Default" });
      tempDirs.push(root);
      try {
        await assertActiveProfile(ctx, "OtherProfile");
        throw new Error("expected CrossProfileMutationError");
      } catch (e) {
        expect(e).toBeInstanceOf(CrossProfileMutationError);
        const err = e as CrossProfileMutationError;
        expect(err.details).toEqual({
          requested: "OtherProfile",
          active: "Default",
          hint: "Use mo2_switch_profile to switch first, or stop MO2 to use offline mutation.",
        });
      }
    });

    it("decodes @ByteArray(\\xHH) in ini fallback so Chinese profile names work end-to-end", async () => {
      // Issue #12 Bug 1 + Bug 2 intersection: the user's real install has
      // selected_profile=@ByteArray(BB84\xe8\x87\xaa\xe7\x94\xa8\x32) which
      // decodes to "BB84自用2". assertActiveProfile must use the decoded form
      // so cross-profile detection works against requests passing the same
      // decoded form (which is what every other tool — Mo2Mo2Modlist,
      // Mo2Mo2ToggleMod — uses).
      const { ctx, root } = await ctxWithStaleBrokerAndIni({
        iniProfile: "BB84\\xe8\\x87\\xaa\\xe7\\x94\\xa8\\x32",
        iniProfileByteArray: true,
      });
      tempDirs.push(root);
      await expect(assertActiveProfile(ctx, "BB84自用2")).resolves.toBeUndefined();
    });

    it("still surfaces non-method_not_found broker errors (does NOT swallow real failures)", async () => {
      const { ctx, root } = await ctxWithStaleBrokerAndIni({
        iniProfile: "Default",
        brokerError: { code: "internal_error", message: "broker exploded" },
      });
      tempDirs.push(root);
      await expect(assertActiveProfile(ctx, "Default")).rejects.toThrow(/broker exploded/);
    });
  });

  it("BUG-21: throws CrossProfileMutationError (not plain Error) on mismatch", async () => {
    try {
      await assertActiveProfile(ctxWithActiveProfile("Default"), "BB84自用");
      throw new Error("expected assertActiveProfile to throw");
    } catch (e) {
      expect(e).toBeInstanceOf(CrossProfileMutationError);
      expect(e).toBeInstanceOf(Error);
      const err = e as CrossProfileMutationError;
      expect(err.code).toBe("cross_profile_live_mutation_blocked");
      expect(err.name).toBe("CrossProfileMutationError");
      expect(err.details).toEqual({
        requested: "BB84自用",
        active: "Default",
        hint: "Use mo2_switch_profile to switch first, or stop MO2 to use offline mutation.",
      });
      expect(err.message).toContain("cross_profile_live_mutation_blocked");
      expect(err.message).toContain("requested='BB84自用'");
      expect(err.message).toContain("active='Default'");
    }
  });
});

describe("CrossProfileMutationError", () => {
  it("is an Error subclass and exposes stable code + details + message", () => {
    const err = new CrossProfileMutationError({ requested: "Alt", active: "Default" });
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(CrossProfileMutationError);
    expect(err.name).toBe("CrossProfileMutationError");
    expect(err.code).toBe("cross_profile_live_mutation_blocked");
    expect(err.details).toEqual({
      requested: "Alt",
      active: "Default",
      hint: "Use mo2_switch_profile to switch first, or stop MO2 to use offline mutation.",
    });
    expect(err.message).toContain("cross_profile_live_mutation_blocked: requested='Alt', active='Default'");
    expect(err.message).toContain("mo2_switch_profile");
  });
});

function dispatchCtx(): ToolContext {
  return {
    config: {
      mo2Root: "/tmp/mo2",
      permissionCeiling: "full-control",
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: "/tmp/mo2/.mo2-mcp/snapshots",
      auditRoot: "/tmp/mo2/.mo2-mcp/audit",
    } as Config,
    sessionId: "profile-guard-dispatch-test",
    plans: new PlanCache(),
    snapshots: new SnapshotManager("/tmp/mo2/.mo2-mcp/snapshots", "profile-guard-dispatch-test"),
    audit: new AuditLogger("/tmp/mo2/.mo2-mcp/audit", "profile-guard-dispatch-test"),
  } as unknown as ToolContext;
}

function responseJson(result: Awaited<ReturnType<typeof dispatchToolCall>>): {
  ok: boolean;
  error?: { code: string; message: string; details?: Record<string, unknown> };
} {
  return JSON.parse(result.content[0].text);
}

describe("dispatch forwards CrossProfileMutationError as structured envelope", () => {
  it("BUG-21: surfaces code='cross_profile_live_mutation_blocked' + details.requested + details.active", async () => {
    _clearToolsForTests();
    registerTool({
      name: "test_cross_profile_failing_tool",
      description: "test-only tool that throws a CrossProfileMutationError",
      tier: "T0",
      inputSchema: z.object({}),
      handler: async () => {
        throw new CrossProfileMutationError({
          requested: "BB84自用",
          active: "Default",
        });
      },
    });

    const result = await dispatchToolCall({
      toolName: "test_cross_profile_failing_tool",
      rawArgs: {},
      ctx: dispatchCtx(),
      rules: [],
    });

    const env = responseJson(result);
    expect(env.ok).toBe(false);
    expect(env.error?.code).toBe("cross_profile_live_mutation_blocked");
    expect(env.error?.code).not.toBe("internal_error");
    expect(env.error?.message).toContain("cross_profile_live_mutation_blocked");
    expect(env.error?.details).toBeDefined();
    expect(env.error?.details?.requested).toBe("BB84自用");
    expect(env.error?.details?.active).toBe("Default");
    expect(env.error?.details?.hint).toContain("mo2_switch_profile");
  });

  it("BUG-21: does NOT collapse CrossProfileMutationError into internal_error envelope", async () => {
    _clearToolsForTests();
    registerTool({
      name: "test_cross_profile_failing_tool_2",
      description: "test-only tool that throws a CrossProfileMutationError",
      tier: "T0",
      inputSchema: z.object({}),
      handler: async () => {
        throw new CrossProfileMutationError({
          requested: "OtherProfile",
          active: "Default",
        });
      },
    });

    const result = await dispatchToolCall({
      toolName: "test_cross_profile_failing_tool_2",
      rawArgs: {},
      ctx: dispatchCtx(),
      rules: [],
    });

    const env = responseJson(result);
    expect(env.ok).toBe(false);
    expect(env.error?.code).toBe("cross_profile_live_mutation_blocked");
    expect(env.error?.code).not.toBe("internal_error");
    expect(env.error?.details?.requested).toBe("OtherProfile");
  });

  it("still routes plain Error instances into internal_error envelope (no regression)", async () => {
    _clearToolsForTests();
    registerTool({
      name: "test_plain_error_after_xprofile_tool",
      description: "test-only tool that throws a plain Error",
      tier: "T0",
      inputSchema: z.object({}),
      handler: async () => {
        throw new Error("something else went wrong");
      },
    });

    const result = await dispatchToolCall({
      toolName: "test_plain_error_after_xprofile_tool",
      rawArgs: {},
      ctx: dispatchCtx(),
      rules: [],
    });

    const env = responseJson(result);
    expect(env.ok).toBe(false);
    expect(env.error?.code).toBe("internal_error");
    expect(env.error?.message).toBe("something else went wrong");
  });
});
