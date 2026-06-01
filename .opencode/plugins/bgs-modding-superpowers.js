// bgs-modding-superpowers — OpenCode plugin entrypoint
//
// Wires three things:
//   1. config.skills.paths: append <plugin>/skills so OpenCode discovers our SKILL.md files
//   2. config.mcp.xedit:    register the bundled xedit-mcp stdio server
//                           (node tools/xedit-mcp/dist/index.js)
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

      // (b) Register the bundled xEdit MCP server via the documented opencode
      //     config.mcp surface. Use ??= so user overrides in opencode.json win.
      //     `enabled: true` is explicit per every real-world LOCAL-stdio MCP
      //     precedent observed in public opencode plugins.
      config.mcp ??= {};
      config.mcp.xedit ??= {
        type: 'local',
        command: ['node', XEDIT_MCP_ENTRY],
        enabled: true,
        environment: {},
        // timeout default is 5000ms; bump if xedit-mcp init grows slow.
      };
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
