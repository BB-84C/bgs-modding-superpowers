import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const entryPath = path.join(root, '.opencode', 'plugins', 'bgs-modding-superpowers.js');
const pluginDirectory = path.join(root, '.opencode', 'plugins');
const helperPath = path.join(root, '.opencode', 'bgs-modding-superpowers-helpers.mjs');
const installPath = path.join(root, '.opencode', 'INSTALL.md');
const readmePath = path.join(root, 'README.md');
const materializerPath = path.join(root, 'scripts', 'build-portable-plugin.ps1');
const integrationPath = path.join(root, 'scripts', 'test-opencode-shared-server.mjs');

const entry = fs.readFileSync(entryPath, 'utf8');
const helper = fs.readFileSync(helperPath, 'utf8');
const guidance = `${fs.readFileSync(installPath, 'utf8')}\n${fs.readFileSync(readmePath, 'utf8')}`;
const materializer = fs.readFileSync(materializerPath, 'utf8');
const integration = fs.readFileSync(integrationPath, 'utf8');

assert.match(entry, /^import BgsModdingSuperpowersPlugin from '\.\.\/bgs-modding-superpowers-helpers\.mjs';/m);
assert.match(entry, /^export default BgsModdingSuperpowersPlugin;$/m);
assert.doesNotMatch(entry, /^export\s+(?:async\s+)?(?:function|const|let|class)\s+/m);
assert.deepEqual(
  fs.readdirSync(pluginDirectory, { withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => entry.name),
  ['bgs-modding-superpowers.js'],
);
assert.match(helper, /export function resolveMcpEntry/);
assert.match(helper, /export async function BgsModdingSuperpowersPlugin/);
assert.match(materializer, /Copy-FileOnly -From "\.opencode\/bgs-modding-superpowers-helpers\.mjs" -To "\.opencode\/bgs-modding-superpowers-helpers\.mjs"/);
assert.match(integration, /RUN_OPENCODE_SHARED_SERVER_TEST/);
assert.doesNotMatch(integration, /4096/);
assert.match(integration, /finally/);
assert.match(integration, /projectWorktreeReturnedThroughServerQuery/);
assert.match(integration, /mcpNamesFoundThroughProjectScopedConfigQuery/);
assert.match(integration, /ownedProcessTreePidCountBeforeTeardown/);
assert.match(integration, /taskkill\.exe/);

assert.doesNotMatch(guidance, /file:\.\//);
assert.doesNotMatch(guidance, /file:\/(?!\/)/);
assert.doesNotMatch(guidance, /["']~\//);
assert.match(guidance, /"\.\/\.opencode\/vendor\/node_modules\/bgs-modding-superpowers"/);
assert.match(guidance, /file:\/\/\//);

console.log('PASS OpenCode plugin entry exports only a default factory');
console.log('PASS OpenCode installation examples use stable project-relative or canonical file URLs');
