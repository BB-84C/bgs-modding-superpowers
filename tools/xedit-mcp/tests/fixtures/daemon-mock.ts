import type { DaemonCall, DaemonAdapter } from "../../src/daemon-adapter.js";

/** In-memory adapter: maps command -> canned daemon result envelope. */
export function makeMockAdapter(
  handlers: Record<string, (args: Record<string, unknown>) => unknown>,
): DaemonAdapter {
  return {
    async call({ command, args }: DaemonCall) {
      const h = handlers[command];
      if (!h) {
        return {
          ok: false,
          command,
          error: { code: "unknown_command", message: `no mock for ${command}` },
        };
      }
      return { ok: true, command, result: h(args ?? {}) };
    },
  };
}
