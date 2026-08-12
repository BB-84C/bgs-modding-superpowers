import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PLUGIN_ROOT = path.resolve(__dirname, '..');
const SKILLS_DIR = path.join(PLUGIN_ROOT, 'skills');
const BOOTSTRAP_SKILL = path.join(SKILLS_DIR, 'using-bgs-modding-superpowers', 'SKILL.md');
const BOOTSTRAP_MARKER = 'EXTREMELY_IMPORTANT_BGS_MODDING_SUPERPOWERS';

function getMcpEntryCandidates(pluginRoot, toolName) {
  const sourceRoot = path.join(pluginRoot, 'tools', toolName);
  return {
    sourceEntry: path.join(sourceRoot, 'dist', 'index.js'),
    sourceNodeModules: path.join(sourceRoot, 'node_modules'),
    portableEntry: path.join(pluginRoot, 'plugins', 'bgs-modding-superpowers', 'tools', toolName, 'dist', 'index.js'),
  };
}

export function resolveMcpEntry(pluginRoot, toolName) {
  const { sourceEntry, sourceNodeModules, portableEntry } = getMcpEntryCandidates(pluginRoot, toolName);
  if (fs.existsSync(sourceEntry) && fs.existsSync(sourceNodeModules)) return sourceEntry;
  if (fs.existsSync(portableEntry)) {
    console.error(`[bgs-modding-superpowers] ${toolName}: using portable-tree MCP entry ${portableEntry}`);
    return portableEntry;
  }
  if (fs.existsSync(sourceEntry)) {
    console.error(`[bgs-modding-superpowers] ${toolName}: using source-tree MCP entry without node_modules ${sourceEntry}`);
    return sourceEntry;
  }
  return null;
}

function logMissingMcpEntry(toolName, pluginRoot) {
  const { sourceEntry, sourceNodeModules, portableEntry } = getMcpEntryCandidates(pluginRoot, toolName);
  console.error(
    `[bgs-modding-superpowers] ${toolName}: MCP server NOT registered; no usable entry found. ` +
      `Checked source entry=${sourceEntry}; source node_modules=${sourceNodeModules}; portable mirror=${portableEntry}. ` +
      'Run npm install and rebuild the MCP server in a dev checkout, or reinstall bgs-modding-superpowers.',
  );
}

function readBootstrap() {
  try {
    return fs.readFileSync(BOOTSTRAP_SKILL, 'utf8');
  } catch {
    return null;
  }
}

export async function BgsModdingSuperpowersPlugin() {
  const bootstrap = readBootstrap();
  return {
    config: async (config) => {
      // Do NOT mutate the passed config object in place. OpenCode invokes plugin
      // config hooks with the workspace's config-state object; when the host
      // workspace has no project-level `mcp`/`skills` config, those fields are
      // references into the process-global config cache. Mutating them writes
      // into shared state visible to every other workspace on the same server.
      // Assign fresh objects instead (same ??=/push semantics, no shared writes).
      const nextSkills = config.skills ?? {};
      config.skills = {
        ...nextSkills,
        paths: nextSkills.paths?.includes(SKILLS_DIR)
          ? nextSkills.paths
          : [...(nextSkills.paths ?? []), SKILLS_DIR],
      };

      const nextMcp = { ...(config.mcp ?? {}) };
      for (const [name, toolName] of [
        ['xedit', 'xedit-mcp'],
        ['bgs_kb', 'bgs-kb-mcp'],
        ['mo2', 'mo2-mcp'],
      ]) {
        const entry = resolveMcpEntry(PLUGIN_ROOT, toolName);
        if (entry) {
          nextMcp[name] ??= {
            type: 'local',
            command: ['node', entry],
            enabled: true,
            environment: {},
            timeout: 240000,
          };
        } else {
          logMissingMcpEntry(toolName, PLUGIN_ROOT);
        }
      }
      config.mcp = nextMcp;
    },
    'experimental.chat.messages.transform': async (_input, output) => {
      if (!bootstrap || !output?.messages?.length) return;
      const firstUser = output.messages.find((message) => message?.info?.role === 'user');
      if (!firstUser?.parts?.length) return;
      if (firstUser.parts.some((part) => part?.type === 'text' && part?.text?.includes(BOOTSTRAP_MARKER))) return;
      firstUser.parts.unshift({ ...firstUser.parts[0], type: 'text', text: bootstrap });
    },
  };
}

export default BgsModdingSuperpowersPlugin;
