import { describe, expect, it } from "vitest";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import {
  acquireLeaseLock,
  acquireLeasesForTargets,
  computeLeaseTargetHash,
  leaseLockPath,
  releaseLeaseLock,
  releaseLeaseLocks,
  type LeaseLockMetadata,
} from "../src/lease-lock.js";

async function tempMo2Root(): Promise<string> {
  return mkdtemp(join(tmpdir(), "lease-lock-"));
}

function metadata(overrides: Partial<LeaseLockMetadata> = {}): LeaseLockMetadata {
  const createdAt = overrides.created_at ?? new Date().toISOString();
  const expiresAt =
    overrides.expires_at ?? new Date(Date.now() + 10 * 60 * 1000).toISOString();
  return {
    plan_id: "plan-a",
    mcp_pid: process.pid,
    mcp_session_id: "session-a",
    lease_token: "lease-token-a",
    tool_name: "mo2_toggle_mod",
    created_at: createdAt,
    expires_at: expiresAt,
    ...overrides,
  };
}

describe("lease-lock", () => {
  it("hashes sorted target paths only", () => {
    const first = computeLeaseTargetHash([
      { path: "B", kind: "directory" },
      { path: "A", kind: "text-file" },
    ]);
    const second = computeLeaseTargetHash([
      { path: "A", kind: "directory" },
      { path: "B", kind: "text-file" },
    ]);
    expect(first).toBe(second);
    expect(first).toMatch(/^[a-f0-9]{64}$/);
  });

  it("refuses a second fresh lock for the same target hash", async () => {
    const root = await tempMo2Root();
    const first = await acquireLeaseLock(root, "hash1", metadata());
    expect(first.acquired).toBe(true);

    const second = await acquireLeaseLock(
      root,
      "hash1",
      metadata({ plan_id: "plan-b", mcp_session_id: "session-b" }),
    );
    expect(second.acquired).toBe(false);
    if (!second.acquired) {
      expect(second.holder).toMatchObject({
        mcp_pid: process.pid,
        tool_name: "mo2_toggle_mod",
      });
    }
  });

  it("re-acquires after matching plan release", async () => {
    const root = await tempMo2Root();
    const first = await acquireLeaseLock(root, "hash1", metadata({ plan_id: "plan-a" }));
    expect(first.acquired).toBe(true);

    await releaseLeaseLock(root, "hash1", "plan-a");

    const second = await acquireLeaseLock(root, "hash1", metadata({ plan_id: "plan-b" }));
    expect(second.acquired).toBe(true);
  });

  it("takes over a lock held by a dead PID", async () => {
    const root = await tempMo2Root();
    await acquireLeaseLock(root, "hash1", metadata({ plan_id: "dead-plan", mcp_pid: 424242 }));

    const replacement = await acquireLeaseLock(
      root,
      "hash1",
      metadata({ plan_id: "replacement-plan" }),
      { isPidAlive: async () => false },
    );

    expect(replacement.acquired).toBe(true);
    const raw = await readFile(leaseLockPath(root, "hash1"), "utf8");
    expect(JSON.parse(raw).plan_id).toBe("replacement-plan");
  });

  it("takes over an expired lock even when the PID is alive", async () => {
    const root = await tempMo2Root();
    await acquireLeaseLock(
      root,
      "hash1",
      metadata({ plan_id: "expired-plan", expires_at: new Date(Date.now() - 1).toISOString() }),
    );

    const replacement = await acquireLeaseLock(
      root,
      "hash1",
      metadata({ plan_id: "replacement-plan" }),
      { isPidAlive: async () => true },
    );

    expect(replacement.acquired).toBe(true);
    const raw = await readFile(leaseLockPath(root, "hash1"), "utf8");
    expect(JSON.parse(raw).plan_id).toBe("replacement-plan");
  });

  it("lets exactly one concurrent acquire win for the same target hash", async () => {
    const root = await tempMo2Root();
    const results = await Promise.all([
      acquireLeaseLock(root, "hash1", metadata({ plan_id: "plan-a" })),
      acquireLeaseLock(root, "hash1", metadata({ plan_id: "plan-b", mcp_session_id: "session-b" })),
    ]);

    expect(results.filter((result) => result.acquired)).toHaveLength(1);
    expect(results.filter((result) => !result.acquired)).toHaveLength(1);
  });

  it("does not release a lock owned by another plan_id", async () => {
    const root = await tempMo2Root();
    await acquireLeaseLock(root, "hash1", metadata({ plan_id: "owner-plan" }));

    await releaseLeaseLock(root, "hash1", "other-plan");

    const raw = await readFile(leaseLockPath(root, "hash1"), "utf8");
    expect(JSON.parse(raw).plan_id).toBe("owner-plan");
  });

  it("tolerates release when the lock file is already gone", async () => {
    const root = await tempMo2Root();
    await expect(releaseLeaseLock(root, "missing", "plan-a")).resolves.toBeUndefined();
  });

  it("treats a malformed existing lock as stale and replaces it", async () => {
    const root = await tempMo2Root();
    const lockPath = leaseLockPath(root, "hash1");
    await mkdir(join(root, ".mo2-mcp", "leases"), { recursive: true });
    await writeFile(lockPath, "not-json", { flag: "wx" });

    const replacement = await acquireLeaseLock(root, "hash1", metadata({ plan_id: "plan-b" }));

    expect(replacement.acquired).toBe(true);
    const raw = await readFile(lockPath, "utf8");
    expect(JSON.parse(raw).plan_id).toBe("plan-b");
  });

  it("retries partial JSON readback before deciding the lock is stale", async () => {
    const root = await tempMo2Root();
    const lockPath = leaseLockPath(root, "hash1");
    await mkdir(join(root, ".mo2-mcp", "leases"), { recursive: true });
    await writeFile(lockPath, '{"plan_id": "plan-a', { flag: "wx" });
    const fullLock = metadata({ plan_id: "plan-a", mcp_session_id: "writer-session" });
    setTimeout(() => {
      void writeFile(lockPath, `${JSON.stringify(fullLock, null, 2)}\n`, "utf8");
    }, 25);

    const second = await acquireLeaseLock(
      root,
      "hash1",
      metadata({ plan_id: "plan-b", mcp_session_id: "second-session" }),
    );

    expect(second.acquired).toBe(false);
    if (!second.acquired) {
      expect(second.holder).toMatchObject({
        mcp_pid: process.pid,
        tool_name: "mo2_toggle_mod",
      });
    }
    const raw = await readFile(lockPath, "utf8");
    expect(JSON.parse(raw).plan_id).toBe("plan-a");
  });

  it("blocks overlapping target sets even when the full target sets differ", async () => {
    const root = await tempMo2Root();
    const first = await acquireLeasesForTargets(
      root,
      [
        { path: "A", kind: "text-file" },
        { path: "B", kind: "text-file" },
      ],
      metadata({ plan_id: "plan-a" }),
    );
    expect(first.acquired).toBe(true);

    const second = await acquireLeasesForTargets(
      root,
      [
        { path: "B", kind: "text-file" },
        { path: "C", kind: "text-file" },
      ],
      metadata({ plan_id: "plan-b", mcp_session_id: "session-b" }),
    );

    expect(second.acquired).toBe(false);
    if (!second.acquired) expect(second.holders).toHaveLength(1);
  });

  it("allows disjoint target sets to acquire concurrently", async () => {
    const root = await tempMo2Root();
    const first = await acquireLeasesForTargets(
      root,
      [
        { path: "A", kind: "text-file" },
        { path: "B", kind: "text-file" },
      ],
      metadata({ plan_id: "plan-a" }),
    );
    const second = await acquireLeasesForTargets(
      root,
      [
        { path: "C", kind: "text-file" },
        { path: "D", kind: "text-file" },
      ],
      metadata({ plan_id: "plan-b", mcp_session_id: "session-b" }),
    );

    expect(first.acquired).toBe(true);
    expect(second.acquired).toBe(true);
  });

  it("blocks subset overlap", async () => {
    const root = await tempMo2Root();
    const first = await acquireLeasesForTargets(
      root,
      [
        { path: "A", kind: "text-file" },
        { path: "B", kind: "text-file" },
      ],
      metadata({ plan_id: "plan-a" }),
    );
    expect(first.acquired).toBe(true);

    const second = await acquireLeasesForTargets(
      root,
      [{ path: "B", kind: "text-file" }],
      metadata({ plan_id: "plan-b", mcp_session_id: "session-b" }),
    );

    expect(second.acquired).toBe(false);
  });

  it("blocks superset overlap", async () => {
    const root = await tempMo2Root();
    const first = await acquireLeasesForTargets(
      root,
      [{ path: "B", kind: "text-file" }],
      metadata({ plan_id: "plan-a" }),
    );
    expect(first.acquired).toBe(true);

    const second = await acquireLeasesForTargets(
      root,
      [
        { path: "A", kind: "text-file" },
        { path: "B", kind: "text-file" },
      ],
      metadata({ plan_id: "plan-b", mcp_session_id: "session-b" }),
    );

    expect(second.acquired).toBe(false);
  });

  it("lets exactly one concurrent overlapping target-set acquire win", async () => {
    const root = await tempMo2Root();
    const results = await Promise.all([
      acquireLeasesForTargets(
        root,
        [
          { path: "A", kind: "text-file" },
          { path: "B", kind: "text-file" },
        ],
        metadata({ plan_id: "plan-a" }),
      ),
      acquireLeasesForTargets(
        root,
        [
          { path: "B", kind: "text-file" },
          { path: "C", kind: "text-file" },
        ],
        metadata({ plan_id: "plan-b", mcp_session_id: "session-b" }),
      ),
    ]);

    expect(results.filter((result) => result.acquired)).toHaveLength(1);
    expect(results.filter((result) => !result.acquired)).toHaveLength(1);
  });

  it("releases all locks acquired for a target set", async () => {
    const root = await tempMo2Root();
    const acquired = await acquireLeasesForTargets(
      root,
      [
        { path: "A", kind: "text-file" },
        { path: "B", kind: "text-file" },
      ],
      metadata({ plan_id: "plan-a" }),
    );
    expect(acquired.acquired).toBe(true);
    if (!acquired.acquired) throw new Error("expected acquisition");

    await releaseLeaseLocks(root, acquired.targetHashes, "plan-a");
    const reacquired = await acquireLeasesForTargets(
      root,
      [{ path: "B", kind: "text-file" }],
      metadata({ plan_id: "plan-b" }),
    );

    expect(reacquired.acquired).toBe(true);
  });
});
