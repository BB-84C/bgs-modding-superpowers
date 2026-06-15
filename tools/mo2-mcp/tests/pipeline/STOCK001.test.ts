import { beforeEach, describe, expect, it, vi } from "vitest";
import { runRules } from "../../src/pipeline/rules.js";
import { stockGameDenyRule } from "../../src/pipeline/rules/STOCK001-stock-game-deny.js";
import { AuditLogger } from "../../src/audit.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import type { ToolContext } from "../../src/types.js";

const moIniState = vi.hoisted(() => ({
  gamePathByRoot: new Map<string, string | null>(),
  throwForRoot: new Set<string>(),
}));

vi.mock("../../src/mo-ini.js", () => ({
  readMoIni: vi.fn(async (iniPath: string) => {
    const root = iniPath.replace(/\\/g, "/").replace(/\/ModOrganizer\.ini$/i, "");
    if (moIniState.throwForRoot.has(root)) throw new Error("missing ini");
    return {
      raw: "",
      general: { gamePath: moIniState.gamePathByRoot.get(root) ?? undefined },
      settings: {},
      customExecutables: [],
      sectionRanges: new Map(),
    };
  }),
}));

let rootCounter = 0;

function nextRoot(): string {
  rootCounter += 1;
  return `C:/MO2-Test-${rootCounter}`;
}

function stubCtx(root: string, deny: string[] = []): ToolContext {
  return {
    config: {
      mo2Root: root,
      permissionCeiling: "metadata-editable" as const,
      allowedProfiles: ["Default"],
      deny,
      snapshotRoot: `${root}/.mo2-mcp/snapshots`,
      auditRoot: `${root}/.mo2-mcp/audit`,
    },
    sessionId: "test-session",
    plans: new PlanCache(),
    snapshots: new SnapshotManager(`${root}/.mo2-mcp/snapshots`, "test-session"),
    audit: new AuditLogger(`${root}/.mo2-mcp/audit`, "test-session"),
  };
}

async function findingsFor(
  args: Record<string, unknown>,
  options: { gamePath?: string | null; deny?: string[]; throwIni?: boolean } = {},
) {
  const root = nextRoot();
  moIniState.gamePathByRoot.set(root, options.gamePath ?? null);
  if (options.throwIni) moIniState.throwForRoot.add(root);
  return runRules([stockGameDenyRule], "mo2_install", stubCtx(root, options.deny ?? []), args);
}

function sourceOf(finding: unknown): string | undefined {
  return (finding as { data?: { source?: string } } | undefined)?.data?.source;
}

describe("STOCK001 game-data-root + user deny patterns", () => {
  beforeEach(() => {
    moIniState.gamePathByRoot.clear();
    moIniState.throwForRoot.clear();
  });

  it("blocks paths under the current ModOrganizer.ini gamePath/Data root", async () => {
    const findings = await findingsFor(
      { archive_path: "C:/Steam/steamapps/common/Fallout 4/Data/evil.esp" },
      { gamePath: "C:/Steam/steamapps/common/Fallout 4" },
    );

    expect(findings[0]?.code).toBe("STOCK001");
    expect(findings[0]?.decision).toBe("block");
    expect(sourceOf(findings[0])).toBe("game_data_root");
    expect(findings[0]?.message).toContain("game_data_root");
  });

  it("blocks Windows-backslash paths under the current gamePath/Data root", async () => {
    const findings = await findingsFor(
      { archive_path: "C:\\Steam\\steamapps\\common\\Fallout 4\\Data\\evil.esp" },
      { gamePath: "C:/Steam/steamapps/common/Fallout 4" },
    );

    expect(findings[0]?.code).toBe("STOCK001");
    expect(sourceOf(findings[0])).toBe("game_data_root");
  });

  it("does not block a different game's Data directory when gamePath points to Fallout 4", async () => {
    const findings = await findingsFor(
      { archive_path: "C:/Steam/steamapps/common/Skyrim Special Edition/Data/x.esm" },
      { gamePath: "C:/Steam/steamapps/common/Fallout 4" },
    );

    expect(findings).toEqual([]);
  });

  it("walks nested arguments recursively", async () => {
    const findings = await findingsFor(
      { mode: "plan", target: { path: "C:/Steam/steamapps/common/Fallout 4/Data/x.esp" } },
      { gamePath: "C:/Steam/steamapps/common/Fallout 4" },
    );

    expect(findings[0]?.code).toBe("STOCK001");
    expect(sourceOf(findings[0])).toBe("game_data_root");
  });

  it("does not error when gamePath is missing and only user deny patterns can apply", async () => {
    const findings = await findingsFor(
      { archive_path: "D:/MO2/Stock Game/Fallout 4/Data/x.esp" },
      { gamePath: null, deny: ["Stock Game/Fallout 4/Data"] },
    );

    expect(findings[0]?.code).toBe("STOCK001");
    expect(sourceOf(findings[0])).toBe("user_deny_pattern");
    expect(findings[0]?.message).toContain("user_deny_pattern: Stock Game/Fallout 4/Data");
  });

  it("does not error when ModOrganizer.ini cannot be read and user deny patterns can apply", async () => {
    const findings = await findingsFor(
      { archive_path: "D:/MO2/Stock Game/Fallout 4/Data/x.esp" },
      { throwIni: true, deny: ["Stock Game/Fallout 4/Data"] },
    );

    expect(findings[0]?.code).toBe("STOCK001");
    expect(sourceOf(findings[0])).toBe("user_deny_pattern");
  });

  it("does not block regular mod overlay Data paths unless they match user deny patterns", async () => {
    const findings = await findingsFor(
      { archive_path: "D:/MO2/mods/SomeMod/Data/x.esp" },
      { gamePath: null, deny: ["Stock Game/Fallout 4/Data"] },
    );

    expect(findings).toEqual([]);
  });

  it("matches user deny patterns case-insensitively as literal substrings", async () => {
    const findings = await findingsFor(
      { archive_path: "D:/Stock Game/Data/x" },
      { gamePath: null, deny: ["stock game/data"] },
    );

    expect(findings[0]?.code).toBe("STOCK001");
    expect(sourceOf(findings[0])).toBe("user_deny_pattern");
  });

  it("is a no-op when gamePath is unavailable and deny list is empty", async () => {
    const missingPathFindings = await findingsFor(
      { archive_path: "D:/MO2/Stock Game/Fallout 4/Data/x.esp" },
      { gamePath: null, deny: [] },
    );
    const unreadableIniFindings = await findingsFor(
      { archive_path: "D:/MO2/Stock Game/Fallout 4/Data/x.esp" },
      { throwIni: true, deny: [] },
    );

    expect(missingPathFindings).toEqual([]);
    expect(unreadableIniFindings).toEqual([]);
  });
});
