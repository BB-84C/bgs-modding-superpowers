import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { expect } from "vitest";

export const PROJECT_ROOT = process.env.BGS_MO2_ACCEPTANCE_PROJECT_ROOT ?? String.raw`D:\awesome-bgs-mod-master`;
export const REAL_MO2_ROOT = process.env.BGS_MO2_ROOT ?? String.raw`B:\WastelandBlues 2.0`;
export const REAL_PROFILE = process.env.BGS_MO2_PROFILE ?? "BB84自用";
export const HARNESS_MO2_ROOT = process.env.BGS_MO2_HARNESS_ROOT ?? String.raw`D:\awesome-bgs-mod-master\.artifacts\mo2`;
export const HARNESS_PROFILE = process.env.BGS_MO2_HARNESS_PROFILE ?? "Default";
export const ARTIFACTS = join(PROJECT_ROOT, ".opencode", "artifacts", "mo2-mcp", "acceptance");
export const MCP_CWD = process.cwd();

export const ACCEPTANCE_MOD = process.env.BGS_MO2_ACCEPTANCE_MOD ?? "LODGen 覆盖素材";
export const ACCEPTANCE_SEPARATOR = process.env.BGS_MO2_ACCEPTANCE_SEPARATOR;
export const ALT_PROFILE = process.env.BGS_MO2_ACCEPTANCE_ALT_PROFILE;
export const FOMOD_ARCHIVE = process.env.BGS_MO2_ACCEPTANCE_FOMOD_ARCHIVE ?? join(ARTIFACTS, "fixtures", "test-fomod.7z");
export const SIMPLE_ARCHIVE = process.env.BGS_MO2_ACCEPTANCE_SIMPLE_ARCHIVE ?? join(ARTIFACTS, "fixtures", "test-simple.7z");
export const OVERRIDDEN_FILE = process.env.BGS_MO2_ACCEPTANCE_OVERRIDDEN_FILE ?? "textures/acceptance/winner.dds";
export const EXPECTED_WINNER = process.env.BGS_MO2_ACCEPTANCE_EXPECTED_WINNER;
export const EXPECTED_ESP_COUNT = Number(process.env.BGS_MO2_ACCEPTANCE_ESP_COUNT ?? "NaN");

export interface ToolResponse {
  ok: boolean;
  result?: any;
  error?: any;
}

export interface McpHandle {
  call: (name: string, args: any) => Promise<ToolResponse>;
  kill: () => void;
}

export async function withMcp<T>(env: Record<string, string>, fn: (mcp: McpHandle) => Promise<T>): Promise<T> {
  const mcp = await spawnMcp(env);
  try {
    return await fn(mcp);
  } finally {
    mcp.kill();
  }
}

export function realEnv(extra: Record<string, string> = {}): Record<string, string> {
  return { BGS_MO2_ROOT: REAL_MO2_ROOT, BGS_MO2_PROFILE: REAL_PROFILE, BGS_MO2_PERMISSION_CEILING: "full-control", ...extra };
}

export function harnessEnv(extra: Record<string, string> = {}): Record<string, string> {
  return { BGS_MO2_ROOT: HARNESS_MO2_ROOT, BGS_MO2_PROFILE: HARNESS_PROFILE, BGS_MO2_PERMISSION_CEILING: "full-control", ...extra };
}

export async function planApply(mcp: McpHandle, tool: string, args: Record<string, unknown>): Promise<{ plan: ToolResponse; apply: ToolResponse }> {
  const plan = await mcp.call(tool, { mode: "plan", ...args });
  expectOk(plan);
  const apply = await mcp.call(tool, {
    mode: "apply",
    plan_id: plan.result.planId,
    lease_token: plan.result.lease_token,
  });
  return { plan, apply };
}

export async function removeModBestEffort(mcp: McpHandle, name: string): Promise<void> {
  const plan = await mcp.call("mo2_remove_mod", { mode: "plan", name, backup_first: false });
  if (!plan.ok) return;
  await mcp.call("mo2_remove_mod", {
    mode: "apply",
    plan_id: plan.result.planId,
    lease_token: plan.result.lease_token,
  });
}

export async function pickFirstMod(mcp: McpHandle, profile: string): Promise<{ name: string; enabled: boolean }> {
  const modlist = await mcp.call("mo2_modlist", { profile });
  expectOk(modlist);
  const mod = (modlist.result.mods as Array<{ name: string; enabled: boolean; is_separator: boolean }>).find((entry) => !entry.is_separator);
  expect(mod).toBeDefined();
  return mod!;
}

export function expectOk(response: ToolResponse): asserts response is ToolResponse & { ok: true; result: any } {
  expect(response.ok, JSON.stringify(response.error ?? response, null, 2)).toBe(true);
}

export async function writeEvidence(name: string, payload: unknown): Promise<void> {
  await mkdir(ARTIFACTS, { recursive: true });
  await writeFile(
    join(ARTIFACTS, `${name}.json`),
    JSON.stringify({ ts: new Date().toISOString(), payload }, null, 2),
    "utf8",
  );
}

export function uniqueName(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function stripCustomExecutables(text: string): string {
  const lines = text.split(/\r?\n/);
  const out: string[] = [];
  let skipping = false;
  for (const line of lines) {
    if (/^\[customExecutables\]$/i.test(line.trim())) {
      skipping = true;
      continue;
    }
    if (skipping && /^\[.+\]$/.test(line.trim())) {
      skipping = false;
    }
    if (!skipping) out.push(line);
  }
  return out.join("\n");
}

export async function spawnMcp(env: Record<string, string>): Promise<McpHandle> {
  const proc = spawn("node", ["dist/index.js"], {
    cwd: MCP_CWD,
    env: { ...process.env, ...env },
    stdio: ["pipe", "pipe", "pipe"],
  }) as ChildProcessWithoutNullStreams;

  let nextId = 1;
  let stdoutBuffer = "";
  let stderrBuffer = "";
  const pending = new Map<number, {
    resolve: (value: any) => void;
    reject: (error: Error) => void;
    timer: ReturnType<typeof setTimeout>;
  }>();

  proc.stderr.on("data", (chunk: Buffer) => {
    stderrBuffer += chunk.toString("utf8");
  });

  proc.stdout.on("data", (chunk: Buffer) => {
    stdoutBuffer += chunk.toString("utf8");
    let idx = stdoutBuffer.indexOf("\n");
    while (idx >= 0) {
      const line = stdoutBuffer.slice(0, idx).trim();
      stdoutBuffer = stdoutBuffer.slice(idx + 1);
      if (line) dispatchJsonRpcLine(line, pending, stderrBuffer);
      idx = stdoutBuffer.indexOf("\n");
    }
  });

  proc.once("exit", (code, signal) => {
    for (const [id, entry] of pending) {
      clearTimeout(entry.timer);
      entry.reject(new Error(`MCP process exited before response id=${id}; code=${code}; signal=${signal}; stderr=${stderrBuffer}`));
    }
    pending.clear();
  });

  const request = (method: string, params: any, timeoutMs = 30_000): Promise<any> => {
    const id = nextId++;
    const payload = { jsonrpc: "2.0", id, method, params };
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`MCP request timed out: ${method}; stderr=${stderrBuffer}`));
      }, timeoutMs);
      pending.set(id, { resolve, reject, timer });
      proc.stdin.write(`${JSON.stringify(payload)}\n`);
    });
  };

  await request("initialize", {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: { name: "mo2-mcp-acceptance", version: "1.0.0" },
  }, 60_000);
  proc.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized", params: {} })}\n`);

  // Wait for binding to settle before returning. The eager-bind code path
  // in main() runs after server.connect(), so `initialize` may return before
  // bind is complete. mo2_session({}) goes through dispatch's awaitSettled
  // hook, so it resolves only after any in-flight bind finishes -- giving us
  // a stable starting state for the rest of the test.
  const sessionResp = await request("tools/call", { name: "mo2_session", arguments: {} }, 60_000);
  const sessionText = sessionResp.result?.content?.[0]?.text;
  if (typeof sessionText === "string") {
    const parsed = JSON.parse(sessionText) as { ok: boolean; snapshot?: { state: string; pipeConnected?: boolean; sidecarReady?: boolean; mo2Root?: string; profile?: string; error?: { code: string; message: string } } };
    const snap = parsed.snapshot;
    if (snap && snap.state !== "bound") {
      throw new Error(`MCP spawned but binding did not reach 'bound' (state=${snap.state}, error=${JSON.stringify(snap.error ?? null)}, pipeConnected=${snap.pipeConnected}, sidecarReady=${snap.sidecarReady}); stderr=${stderrBuffer}`);
    }
  }

  return {
    call: async (name: string, args: any): Promise<ToolResponse> => {
      const response = await request("tools/call", { name, arguments: args }, 180_000);
      const text = response.result?.content?.[0]?.text;
      if (typeof text !== "string") {
        return { ok: false, error: { code: "malformed_mcp_response", response } };
      }
      try {
        return JSON.parse(text) as ToolResponse;
      } catch (error) {
        return { ok: false, error: { code: "tool_response_not_json", message: String(error), text } };
      }
    },
    kill: () => {
      for (const [id, entry] of pending) {
        clearTimeout(entry.timer);
        entry.reject(new Error(`MCP process killed before response id=${id}`));
      }
      pending.clear();
      proc.stdin.end();
      proc.kill();
    },
  };
}

function dispatchJsonRpcLine(
  line: string,
  pending: Map<number, { resolve: (value: any) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> }>,
  stderrBuffer: string,
): void {
  let message: any;
  try {
    message = JSON.parse(line);
  } catch {
    return;
  }
  if (typeof message.id !== "number") return;
  const entry = pending.get(message.id);
  if (!entry) return;
  pending.delete(message.id);
  clearTimeout(entry.timer);
  if (message.error) {
    entry.reject(new Error(`MCP JSON-RPC error id=${message.id}: ${JSON.stringify(message.error)}; stderr=${stderrBuffer}`));
  } else {
    entry.resolve(message);
  }
}
