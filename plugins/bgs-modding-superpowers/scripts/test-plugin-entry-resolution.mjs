import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { resolveMcpEntry } from '../.opencode/plugins/bgs-modding-superpowers.js';

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
