// bgs-modding-superpowers — OpenCode plugin entrypoint
//
// Wires three things:
//   1. config.skills.paths: append <plugin>/skills so OpenCode discovers our SKILL.md files
//   2. config.mcp.xedit + config.mcp.bgs_kb + config.mcp.mo2:
//                           register the bundled MCP stdio servers
//                           (node tools/<server>/dist/index.js)
//   3. first-user-message bootstrap: inject the using-bgs-modding-superpowers SKILL body
//                                    into the first user message so the host agent loads
//                                    the bootstrap on every session start
//
// Pattern adapted from obra/superpowers/.opencode/plugins/superpowers.js (for skills + bootstrap
// injection) and alvinunreal/oh-my-opencode-slim (for the local-MCP config.mcp surface).

import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// .opencode/plugins/<file>.js lives two dirs below the plugin root
const PLUGIN_ROOT = path.resolve(__dirname, '..', '..');

const SKILLS_DIR = path.join(PLUGIN_ROOT, 'skills');
const XEDIT_MCP_ENTRY = path.join(PLUGIN_ROOT, 'tools', 'xedit-mcp', 'dist', 'index.js');
const BGS_KB_MCP_ENTRY = path.join(PLUGIN_ROOT, 'tools', 'bgs-kb-mcp', 'dist', 'index.js');
const MO2_MCP_ENTRY = path.join(PLUGIN_ROOT, 'tools', 'mo2-mcp', 'dist', 'index.js');
const BOOTSTRAP_SKILL = path.join(SKILLS_DIR, 'using-bgs-modding-superpowers', 'SKILL.md');

// Sentinel used to detect already-injected bootstrap so we don't double-inject across reloads.
const BOOTSTRAP_MARKER = 'EXTREMELY_IMPORTANT_BGS_MODDING_SUPERPOWERS';

function readBootstrap() {
  try {
    return fs.readFileSync(BOOTSTRAP_SKILL, 'utf8');
  } catch (err) {
    // Bootstrap skill not present yet (e.g., before P2 in the reshape plan).
    // Plugin still loads; first-user-message injection is just a no-op.
    return null;
  }
}

// mo2-mcp's index.ts hard-requires BGS_MO2_ROOT at startup; if missing it
// writes "BGS_MO2_ROOT not set\n" to stderr and process.exit(1). That kills
// stdio before MCP handshake completes, which OpenCode surfaces as
//   "mo2 MCP error -32000: Connection closed".
// detectMo2Root resolves a sensible default before we register the server:
//   1. explicit process.env.BGS_MO2_ROOT wins (lets the user override)
//   2. <PLUGIN_ROOT>/.artifacts/mo2 covers dev work in the awesome-bgs-mod-master
//      repo (the canonical low-noise harness MO2)
//   3. process.cwd() covers vendor-clone users running OpenCode at their own
//      MO2 project root (the workspace cwd contains ModOrganizer.exe).
// If none of those resolves, we skip registering mo2 entirely instead of
// letting it crash on startup; the user can set BGS_MO2_ROOT and restart
// OpenCode to bring it online.
function detectMo2Root() {
  if (process.env.BGS_MO2_ROOT) return process.env.BGS_MO2_ROOT;
  const candidates = [
    path.join(PLUGIN_ROOT, '.artifacts', 'mo2'),
    process.cwd(),
  ];
  for (const c of candidates) {
    try {
      if (fs.existsSync(path.join(c, 'ModOrganizer.exe'))) return c;
    } catch {
      // ignore stat failures; try next candidate
    }
  }
  return undefined;
}

export const BgsModdingSuperpowersPlugin = async () => {
  const bootstrap = readBootstrap();

  return {
    // NOTE: `mcp:` on the plugin return is NOT a documented Hook key in
    // @opencode-ai/plugin's Hooks interface and is silently ignored by
    // current OpenCode. The `config:` hook below is the only canonical
    // surface for registering plugin-bundled MCP servers. (Verified against
    // anomalyco/opencode upstream Hooks definition + real precedents like
    // vercel-labs/coding-agent-template, glommer/memelord.)

    config: async (config) => {
      // (a) Make our skills discoverable by appending to config.skills.paths.
      config.skills ??= {};
      config.skills.paths ??= [];
      if (!config.skills.paths.includes(SKILLS_DIR)) {
        config.skills.paths.push(SKILLS_DIR);
      }

      // (b) Register the bundled MCP servers via the documented opencode
      //     config.mcp surface. Use ??= so user overrides in opencode.json win.
      //     `enabled: true` is explicit per every real-world LOCAL-stdio MCP
      //     precedent observed in public opencode plugins.
      //
      //     timeout = 240s because the first xedit_session call lazily starts
      //     the xEdit daemon via MO2's control plane, which takes ~60-180s.
      //     Subsequent calls are fast (the toolset is cached for the server's
      //     lifetime). The default 5s timeout would always trip on first call.
      config.mcp ??= {};
      config.mcp.xedit ??= {
        type: 'local',
        command: ['node', XEDIT_MCP_ENTRY],
        enabled: true,
        environment: {},
        timeout: 240000,
      };
      config.mcp.bgs_kb ??= {
        type: 'local',
        command: ['node', BGS_KB_MCP_ENTRY],
        enabled: true,
        environment: {},
        timeout: 240000,
      };
      // mo2-mcp: agent-facing MO2 control plane (34 tools across read/metadata/mutating
      // tiers, plan/apply with leases, JSONL audit). Talks to the bundled control-plane
      // Python broker over named pipe + the bundled Python sidecar over JSON-RPC. The
      // first call lazily spins up the sidecar Python process; 240s timeout matches the
      // xedit lane for consistency, but warm calls return in tens of ms.
      //
      // Registration is gated on detectMo2Root() finding a real MO2 install — without
      // BGS_MO2_ROOT mo2-mcp would crash at startup ("Connection closed -32000"), so we
      // simply do not register when no candidate resolves. Set BGS_MO2_ROOT explicitly
      // and restart OpenCode to bring mo2 online in that case.
      if (config.mcp.mo2 === undefined) {
        const detectedMo2Root = detectMo2Root();
        if (detectedMo2Root) {
          config.mcp.mo2 = {
            type: 'local',
            command: ['node', MO2_MCP_ENTRY],
            enabled: true,
            environment: { BGS_MO2_ROOT: detectedMo2Root },
            timeout: 240000,
          };
        }
      }
    },

    // (d) Inject the bootstrap skill body into the first user message of each session.
    //     Using a user message (not system) avoids:
    //       1. Token bloat from system messages repeated every turn
    //       2. Multiple system messages breaking some non-Anthropic models
    //     Matches the pattern in obra/superpowers/.opencode/plugins/superpowers.js.
    'experimental.chat.messages.transform': async (_input, output) => {
      if (!bootstrap || !output?.messages?.length) return;
      const firstUser = output.messages.find((m) => m?.info?.role === 'user');
      if (!firstUser?.parts?.length) return;
      // Idempotency: skip if any part already carries the marker.
      if (firstUser.parts.some((p) => p?.type === 'text' && p?.text?.includes(BOOTSTRAP_MARKER))) {
        return;
      }
      const ref = firstUser.parts[0];
      firstUser.parts.unshift({ ...ref, type: 'text', text: bootstrap });
    },
  };
};

export default BgsModdingSuperpowersPlugin;
