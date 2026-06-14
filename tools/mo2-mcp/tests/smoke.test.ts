import { describe, it, expect } from "vitest";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";

async function _fixtureMo2Root(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "mo2-smoke-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "", "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\n[Settings]\nbase_directory=" + root + "\n",
    "utf8",
  );
  await mkdir(join(root, "mods"), { recursive: true });
  return root;
}

describe("mo2-mcp smoke", () => {
  it("server starts, tools/list returns registered S3A tools, clean shutdown", async () => {
    const mo2Root = await _fixtureMo2Root();
    const env = { ...process.env, BGS_MO2_ROOT: mo2Root };

    const proc = spawn("node", ["./dist/index.js"], {
      stdio: ["pipe", "pipe", "pipe"],
      env,
      cwd: process.cwd(),
    });

    // Wait for stderr "ready" signal or stdout JSON-RPC handshake initiation
    const ready = new Promise<void>((resolve) => {
      const onStderr = (chunk: Buffer): void => {
        if (chunk.toString("utf8").includes("ready")) {
          proc.stderr.off("data", onStderr);
          resolve();
        }
      };
      proc.stderr.on("data", onStderr);
    });

    // Send MCP initialize handshake
    const init = {
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: { name: "smoke-test", version: "0.0.0" },
      },
    };
    proc.stdin.write(JSON.stringify(init) + "\n");

    // Send tools/list
    const list = { jsonrpc: "2.0", id: 2, method: "tools/list", params: {} };

    // Collect responses
    let stdoutBuffer = "";
    const responseHandler = new Promise<string>((resolve) => {
      const onData = (chunk: Buffer): void => {
        stdoutBuffer += chunk.toString("utf8");
        if (stdoutBuffer.includes('"id":2')) {
          proc.stdout.off("data", onData);
          resolve(stdoutBuffer);
        }
      };
      proc.stdout.on("data", onData);
    });

    // Wait a beat then send list request
    await new Promise((r) => setTimeout(r, 500));
    proc.stdin.write(JSON.stringify(list) + "\n");

    try {
      const responses = await Promise.race([
        responseHandler,
        new Promise<string>((_, reject) =>
          setTimeout(() => reject(new Error("smoke timeout")), 10000),
        ),
      ]);

      // Find the tools/list response (id=2)
      const lines = responses.split("\n").filter((l) => l.trim());
      const toolsListLine = lines.find((l) => l.includes('"id":2'));
      expect(toolsListLine).toBeDefined();
      const parsed = JSON.parse(toolsListLine!);
      expect(parsed.id).toBe(2);
      expect(parsed.result).toBeDefined();
      expect(parsed.result.tools.map((tool: { name: string }) => tool.name)).toEqual([
        "mo2_status",
        "mo2_machine_contract",
        "mo2_modlist",
        "mo2_pluginlist",
      ]);
    } finally {
      void ready;
      proc.stdin.end();
      proc.kill();
    }
  }, 15000);
});
