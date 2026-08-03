import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import BgsModdingSuperpowersPlugin, { resolveMcpEntry } from '../.opencode/bgs-modding-superpowers-helpers.mjs';

const toolName = 'mo2-mcp';

function touch(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, '');
}

function sourceEntry(root) {
  return path.join(root, 'tools', toolName, 'dist', 'index.js');
}

function sourceNodeModules(root) {
  return path.join(root, 'tools', toolName, 'node_modules');
}

function portableEntry(root) {
  return path.join(root, 'plugins', 'bgs-modding-superpowers', 'tools', toolName, 'dist', 'index.js');
}

function makeRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'bgs-plugin-entry-'));
}

function withFixture(name, setup, expected) {
  const root = makeRoot();
  try {
    setup(root);
    const actual = resolveMcpEntry(root, toolName);
    assert.equal(actual, expected(root));
    console.log(`PASS ${name}`);
  } catch (err) {
    console.error(`FAIL ${name}`);
    throw err;
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

withFixture(
  'dev-checkout resolves source-tree entry when entry and node_modules exist',
  (root) => {
    touch(sourceEntry(root));
    touch(path.join(sourceNodeModules(root), '.keep'));
  },
  sourceEntry,
);

withFixture(
  'git-spec clone resolves portable mirror when source node_modules are absent',
  (root) => {
    touch(sourceEntry(root));
    touch(portableEntry(root));
  },
  portableEntry,
);

withFixture(
  'portable-as-root falls back to source entry when no node_modules or mirror exist',
  (root) => {
    touch(sourceEntry(root));
  },
  sourceEntry,
);

withFixture(
  'nothing usable resolves to null',
  () => {},
  () => null,
);

const plugin = await BgsModdingSuperpowersPlugin();
const config = { mcp: { xedit: { userOverride: true } } };
await plugin.config(config);
assert.equal(config.mcp.xedit.userOverride, true);
assert.deepEqual(Object.keys(config.mcp).sort(), ['bgs_kb', 'mo2', 'xedit']);
assert.ok(config.skills.paths.some((entry) => entry.endsWith(path.join('skills'))));
for (const name of ['bgs_kb', 'mo2']) {
  assert.equal(config.mcp[name].type, 'local');
  assert.equal(config.mcp[name].command[0], 'node');
  assert.ok(config.mcp[name].command[1].endsWith(path.join('dist', 'index.js')));
}
console.log('PASS helper registers skills and all three MCP servers without replacing user overrides');
