import { describe, it, expect } from "vitest";
import { xeditListCapabilitiesTool } from "../../src/tools/list-capabilities.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";

const ctx: ToolContext = {
  sessionId: "s",
  daemonPid: 1234,
  capabilities: {
    contractVersion: "0.10",
    gameMode: "Fallout4",
    commands: ["system.describe", "records.get", "records.brand_new_thing"],
    fetchedAt: "now",
  },
};

describe("xedit_list_capabilities tool", () => {
  it("returns the curated digest + drift report against live commands", async () => {
    const adapter = makeMockAdapter({});
    const tool = xeditListCapabilitiesTool({ adapter, getContext: () => ctx });
    const env = await tool({});
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    const data = env.data as {
      contractVersion: string;
      groups: unknown[];
      drift: { onlyInDigest: string[]; onlyInLive: string[] };
    };
    expect(data.contractVersion).toBe("0.10");
    expect(data.groups.length).toBeGreaterThan(0);
    expect(data.drift.onlyInLive).toContain("records.brand_new_thing");
    expect(data.drift.onlyInDigest.length).toBeGreaterThan(0);
  });

  it("refuses if session context not yet built", async () => {
    const adapter = makeMockAdapter({});
    const tool = xeditListCapabilitiesTool({ adapter, getContext: () => undefined });
    const env = await tool({});
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("state_violation");
    expect(env.hint).toContain("xedit_session");
  });
});
