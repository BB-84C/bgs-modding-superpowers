# mo2-vfs-launcher

`mo2-vfs-launcher` is a small wrapper around `mo2-vfs-launcher.ps1` for launching a caller-provided target inside an already-established MO2/usvfs context.

The launcher is a control-plane launch consumer: it shapes launcher-specific target state, but broker-backed transport owns process start and wait behavior when the control-plane launch family is available.

`mo2-vfs-probe.ps1` is a read-only helper that emits one-line JSON showing whether a caller-provided path and `%LOCALAPPDATA%\Fallout4\plugins.txt` are visible from the current process context.

## Contract

- `--target-path` is the required target path to the script or executable that should run inside the MO2 VFS context.
- `--target-arg` can be repeated to forward arguments to the target path in order.
- `--env` supports environment injection with `NAME=value` entries that are applied to the launched target process.
- `--session-id` and `--state-file` are required so the launcher can write its consumer-facing JSON state file for orchestration and evidence capture.
- `--wait-mode` controls wait mode and supports `spawned` and `exit`.
- Failure behavior is fail-closed: invalid input, timeouts, and non-zero target exits writes a failed state to the state file and return a non-zero exit code.

## Usage

PowerShell:

```powershell
pwsh -NoProfile -File .\tools\mo2-vfs-launcher\mo2-vfs-launcher.ps1 \
  --target-path .\tools\mo2-vfs-launcher\some-target.ps1 \
  --session-id session-001 \
  --state-file .\.artifacts\mo2-vfs-launcher\session-001.json \
  --wait-mode exit \
  --env FOO=bar \
  --target-arg first
```

CMD wrapper:

```bat
tools\mo2-vfs-launcher\mo2-vfs-launcher.cmd --target-path tools\mo2-vfs-launcher\some-target.ps1 --session-id session-001 --state-file .artifacts\mo2-vfs-launcher\session-001.json --wait-mode spawned
```

MO2 handoff pattern:

```powershell
& "B:\WastelandBlues 2.0\ModOrganizer.exe" -p "CK与调试" run -e OpenCodeVfsLauncher -a "--target-path D:\awesome-bgs-mod-master\.worktrees\mo2-vfs-launcher\tools\mo2-vfs-launcher\some-target.ps1 --session-id session-001 --state-file D:\awesome-bgs-mod-master\.worktrees\mo2-vfs-launcher\.artifacts\mo2-vfs-launcher\session-001.json --wait-mode exit"
```

The MO2 `run -e OpenCodeVfsLauncher` pattern is a launcher bootstrap entrypoint, not the long-term transport architecture center. Once the launcher is running inside the MO2/usvfs context, it should hand target execution off to the control-plane launch abstraction and then publish launcher-shaped state back through `--state-file`.

Probe usage:

```powershell
pwsh -NoProfile -File .\tools\mo2-vfs-launcher\mo2-vfs-probe.ps1 --path .\tools\mo2-vfs-launcher\some-target.ps1
```
