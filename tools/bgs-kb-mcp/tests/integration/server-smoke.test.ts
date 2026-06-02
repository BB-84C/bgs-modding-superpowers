import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { resolve } from "node:path";
import { afterEach, describe, expect, test } from "vitest";

const integrationEnabled = process.env.BGS_KB_MCP_INTEGRATION === "1";

interface JsonRpcMessage {
  id?: number;
  result?: unknown;
  error?: unknown;
}

const children: ChildProcessWithoutNullStreams[] = [];

afterEach(async () => {
  await Promise.all(children.splice(0).map((child) => stopChild(child)));
});

function stopChild(child: ChildProcessWithoutNullStreams): Promise<void> {
  if (child.exitCode !== null || child.signalCode !== null) return Promise.resolve();
  return new Promise((resolveStop) => {
    child.once("close", () => resolveStop());
    child.kill("SIGTERM");
    setTimeout(() => {
      if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL");
    }, 2_000).unref();
  });
}

function startServer(): { child: ChildProcessWithoutNullStreams; messages: JsonRpcMessage[]; stderr: string[] } {
  const child = spawn(process.execPath, [resolve("dist", "index.js")], {
    cwd: resolve("."),
    stdio: ["pipe", "pipe", "pipe"],
  });
  children.push(child);

  const messages: JsonRpcMessage[] = [];
  const stderr: string[] = [];
  let stdoutBuffer = "";
  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk: string) => {
    stdoutBuffer += chunk;
    for (;;) {
      const newline = stdoutBuffer.indexOf("\n");
      if (newline < 0) break;
      const line = stdoutBuffer.slice(0, newline).trim();
      stdoutBuffer = stdoutBuffer.slice(newline + 1);
      if (line.length > 0) messages.push(JSON.parse(line) as JsonRpcMessage);
    }
  });
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk: string) => stderr.push(chunk));
  return { child, messages, stderr };
}

async function waitForResponses(messages: JsonRpcMessage[], count: number, stderr: string[]): Promise<void> {
  const deadline = Date.now() + 8_000;
  while (messages.length < count) {
    if (Date.now() > deadline) {
      throw new Error(`Timed out waiting for ${count} JSON-RPC responses; got ${messages.length}; stderr=${stderr.join("")}`);
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 25));
  }
}

function send(child: ChildProcessWithoutNullStreams, message: Record<string, unknown>): void {
  child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", ...message })}\n`);
}

function resultById<T>(messages: JsonRpcMessage[], id: number): T {
  const message = messages.find((candidate) => candidate.id === id);
  expect(message?.error).toBeUndefined();
  expect(message?.result).toBeDefined();
  return message!.result as T;
}

function parseToolBody(result: { content: Array<{ type: string; text: string }> }): Record<string, unknown> {
  expect(result.content[0].type).toBe("text");
  return JSON.parse(result.content[0].text) as Record<string, unknown>;
}

describe.skipIf(!integrationEnabled)("KB-2f stdio MCP server smoke", () => {
  test("serves initialize, tools/list, status, and query over newline JSON-RPC", async () => {
    const { child, messages, stderr } = startServer();

    send(child, {
      id: 1,
      method: "initialize",
      params: { protocolVersion: "2024-11-05", capabilities: {}, clientInfo: { name: "kb-smoke", version: "0.0.0" } },
    });
    send(child, { id: 2, method: "tools/list", params: {} });
    send(child, { id: 3, method: "tools/call", params: { name: "bgs_kb_status", arguments: {} } });
    send(child, { id: 4, method: "tools/call", params: { name: "bgs_kb_query", arguments: { query: "plugins", maxResults: 3 } } });

    await waitForResponses(messages, 4, stderr);

    const initialized = resultById<{ serverInfo: { name: string; version: string } }>(messages, 1);
    expect(initialized.serverInfo.name).toBe("bgs-kb-mcp");

    const listed = resultById<{ tools: Array<{ name: string }> }>(messages, 2);
    expect(listed.tools.map((tool) => tool.name)).toEqual(["bgs_kb_status", "bgs_kb_query", "bgs_kb_get"]);

    const status = parseToolBody(resultById<{ content: Array<{ type: string; text: string }> }>(messages, 3));
    expect(status.ok).toBe(true);
    const statusData = status.data as { packs: Array<{ packId: string }>; totalRecordCount: number };
    expect(statusData.packs).toHaveLength(1);
    expect(statusData.packs[0].packId).toBe("bgs-kb-core");
    expect(statusData.totalRecordCount).toBe(46);

    const query = parseToolBody(resultById<{ content: Array<{ type: string; text: string }> }>(messages, 4));
    expect(query.ok).toBe(true);
    const queryData = query.data as { hits: unknown[] };
    expect(queryData.hits.length).toBeGreaterThanOrEqual(1);
  });
});
