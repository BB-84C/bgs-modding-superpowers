import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';

if (process.env.RUN_OPENCODE_SHARED_SERVER_TEST !== '1') {
  console.log('SKIP shared-server integration: set RUN_OPENCODE_SHARED_SERVER_TEST=1 to launch an owned disposable child.');
  process.exit(0);
}

const projectDirectory = path.resolve(import.meta.dirname, '..');
const capturePath = process.env.OPENCODE_INTEGRATION_CAPTURE ?? path.join(
  projectDirectory,
  '.opencode',
  'artifacts',
  'open-issues-25-29',
  'issue-25',
  'shared-server-integration.json',
);
const binary = process.env.OPENCODE_BINARY ?? path.join(
  process.env.APPDATA ?? '',
  'npm',
  'node_modules',
  'opencode-ai',
  'bin',
  process.platform === 'win32' ? 'opencode.exe' : 'opencode',
);

if (!fs.existsSync(binary)) {
  throw new Error(`OpenCode binary not found at ${binary}. Set OPENCODE_BINARY to the real executable; do not use a wrapper script.`);
}
if (process.platform !== 'win32') {
  throw new Error('This owned-process integration test currently has a Windows process-tree cleanup implementation only.');
}

function reservePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close((error) => (error ? reject(error) : resolve(port)));
    });
  });
}

function waitForExit(child, timeoutMs = 10_000) {
  if (child.exitCode !== null || child.signalCode !== null) {
    return Promise.resolve({ code: child.exitCode, signal: child.signalCode });
  }
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`Owned OpenCode child ${child.pid} did not exit after teardown.`)), timeoutMs);
    child.once('exit', (code, signal) => {
      clearTimeout(timer);
      resolve({ code, signal });
    });
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function windowsProcessSnapshot() {
  const result = spawnSync('powershell.exe', [
    '-NoProfile',
    '-NonInteractive',
    '-Command',
    'Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,CreationDate,Name,ExecutablePath | ConvertTo-Json -Compress',
  ], { encoding: 'utf8', timeout: 30_000 });
  assert.equal(result.error, undefined, `Could not inspect the owned OpenCode process tree: ${result.error?.message}`);
  assert.equal(result.status, 0, `Could not inspect the owned OpenCode process tree: ${result.stderr}`);
  const rows = JSON.parse(result.stdout);
  return new Map((Array.isArray(rows) ? rows : [rows]).map((row) => [Number(row.ProcessId), row]));
}

function ownedProcessTree(rootPid) {
  const processes = windowsProcessSnapshot();
  const root = processes.get(rootPid);
  assert.ok(root, `Owned OpenCode child ${rootPid} disappeared before process-tree accounting.`);
  assert.equal(Number(root.ParentProcessId), process.pid, 'Refusing tree cleanup: the server PID is not a direct child of this test.');
  assert.equal(path.basename(root.ExecutablePath).toLowerCase(), 'opencode.exe', 'Refusing tree cleanup: the direct child is not OpenCode.');

  const owned = new Map([[rootPid, root]]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const processInfo of processes.values()) {
      const pid = Number(processInfo.ProcessId);
      if (!owned.has(pid) && owned.has(Number(processInfo.ParentProcessId))) {
        owned.set(pid, processInfo);
        changed = true;
      }
    }
  }
  return [...owned.values()];
}

function terminateOwnedProcessTree(rootPid) {
  const result = spawnSync('taskkill.exe', ['/PID', String(rootPid), '/T', '/F'], {
    encoding: 'utf8',
    timeout: 30_000,
    windowsHide: true,
  });
  assert.equal(result.error, undefined, `Could not terminate the owned OpenCode process tree: ${result.error?.message}`);
  assert.equal(result.status, 0, `Could not terminate the owned OpenCode process tree: ${result.stderr || result.stdout}`);
}

async function getProjectJson(port, password, endpoint) {
  const url = new URL(`http://127.0.0.1:${port}${endpoint}`);
  url.searchParams.set('directory', projectDirectory);
  const response = await fetch(url, {
    headers: {
      authorization: `Basic ${Buffer.from(`opencode:${password}`).toString('base64')}`,
    },
  });
  if (!response.ok) {
    throw new Error(`Project-scoped ${endpoint} query failed with HTTP ${response.status}: ${(await response.text()).slice(0, 500)}`);
  }
  return response.json();
}

async function waitForProjectQuery(port, password) {
  const deadline = Date.now() + 15_000;
  let lastError;
  while (Date.now() < deadline) {
    try {
      return await getProjectJson(port, password, '/project/current');
    } catch (error) {
      lastError = error;
      await sleep(100);
    }
  }
  throw new Error(`Owned OpenCode server never accepted a project-scoped API query: ${lastError?.message}`);
}

const port = await reservePort();
const serverCwd = fs.mkdtempSync(path.join(os.tmpdir(), 'bgs-opencode-shared-server-'));
const password = `task2-${randomUUID()}`;
const child = spawn(binary, ['serve', '--port', String(port)], {
  cwd: serverCwd,
  env: { ...process.env, OPENCODE_SERVER_PASSWORD: password },
  stdio: 'ignore',
  windowsHide: true,
});

let project;
let skills;
let projectConfig;
let observedMcpNames = [];
let accountedOwnedProcesses = [];
let exit;
try {
  console.log('INFO querying the project through the owned server');
  project = await waitForProjectQuery(port, password);
  assert.equal(path.resolve(project.worktree).toLowerCase(), projectDirectory.toLowerCase(), 'The server did not attach the requested project directory.');

  [skills, projectConfig] = await Promise.all([
    getProjectJson(port, password, '/skill'),
    getProjectJson(port, password, '/config'),
  ]);
  assert.ok(skills.some((skill) => skill.name === 'using-bgs-modding-superpowers'), 'Project-scoped server skill query did not expose the BGS bootstrap skill.');
  for (const name of ['xedit', 'bgs_kb', 'mo2']) {
    assert.ok(Object.hasOwn(projectConfig.mcp, name), `Project-scoped server config query did not expose ${name}.`);
  }
  observedMcpNames = Object.keys(projectConfig.mcp).filter((name) => ['xedit', 'bgs_kb', 'mo2'].includes(name));
  accountedOwnedProcesses = ownedProcessTree(child.pid);
} finally {
  if (child.exitCode === null) {
    console.log('INFO tearing down the owned server process tree');
    const ownedNow = ownedProcessTree(child.pid);
    accountedOwnedProcesses = [...new Map([...accountedOwnedProcesses, ...ownedNow]
      .map((processInfo) => [Number(processInfo.ProcessId), processInfo])).values()];
    terminateOwnedProcessTree(child.pid);
  }
  exit = await waitForExit(child);
  await sleep(250);
  const remaining = windowsProcessSnapshot();
  const ownedPids = accountedOwnedProcesses.map((processInfo) => Number(processInfo.ProcessId));
  assert.ok(ownedPids.every((pid) => !remaining.has(pid)), `Owned OpenCode process tree still has live PIDs: ${ownedPids.filter((pid) => remaining.has(pid)).join(', ')}`);
  fs.rmSync(serverCwd, { recursive: true, force: true });
}

const rebind = net.createServer();
await new Promise((resolve, reject) => {
  rebind.once('error', reject);
  rebind.listen(port, '127.0.0.1', resolve);
});
await new Promise((resolve, reject) => rebind.close((error) => (error ? reject(error) : resolve())));

fs.mkdirSync(path.dirname(capturePath), { recursive: true });
fs.writeFileSync(capturePath, `${JSON.stringify({
  serverWorkingDirectory: serverCwd,
  projectWorktreeReturnedThroughServerQuery: project.worktree,
  skillNameFoundThroughProjectScopedServerQuery: skills.find((skill) => skill.name === 'using-bgs-modding-superpowers').name,
  mcpNamesFoundThroughProjectScopedConfigQuery: observedMcpNames,
  ownedProcessTreePidCountBeforeTeardown: accountedOwnedProcesses.length,
  ownedServerExit: exit,
  portRebindAfterOwnedTreeTeardown: true,
}, null, 2)}\n`);
console.log(`PASS server cwd differed from project cwd; project-scoped server queries exposed the BGS skill and xedit/bgs_kb/mo2 configuration; ${accountedOwnedProcesses.length} owned process-tree PID(s) were torn down and port ${port} rebound.`);
