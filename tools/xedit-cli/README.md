# xedit-cli

This directory is reserved for the primary public wrapper that orchestrates upstream xEdit through wrapper-owned Pascal scripts.

The wrapper should keep xEdit external and treat it as the execution engine.

Phase 1 is a safe, read-only workflow focused on conflict indexing and record inspection.

The current slice now accepts a caller-provided launcher path for `doctor env`, validates an optional xEdit PID, and implements PID-based process lifecycle commands while keeping the live-run path as the target contract.

The runtime target is `xedit-cli -> control plane -> mo2-vfs-launcher -> xEdit`. xedit-cli should launch through the MO2 control plane, with mo2-vfs-launcher as the generic VFS-side child launcher. The control plane chooses and brokers the MO2-facing launch, and the launcher is only the VFS-side child process seam into xEdit.

The approved step-1 target contract keeps a step-1 hook bridge for `Module Selection`, but the runtime contract is now a single `load` semantic instead of subset-era wrapper modes. The caller provides or implies the plugin set for the launch, `xedit-cli` materializes that set into a session-scoped `plugins.txt`, and xEdit consumes it through the xEdit native `-P:` seam.

MO2/usvfs owns the real plugin/file-tree semantics, and the MO2-backed environment remains the source of truth for full plugin order. The wrapper uses that environment to resolve the requested load set, writes the canonical session file under the launch session directory, and the real MO2 profile `plugins.txt` remains untouched.

The same no-fork `hook.dll` bridge remains useful for launch/session plumbing around `Module Selection`, but its contract is now auto-confirm and diagnostics only. Current HWND/tree probing remains diagnostic only, and hook.dll owns only xEdit in-process automation rather than any model-layer subset behavior.

Launcher-driven commands require authoritative `--game-mode`. `--game-mode` is the primary trust and control signal for mode selection, not executable-name-derived guessing. The CLI maps `Fallout4` to `-FO4`, `Skyrim` to `-TES5`, `SkyrimSE` to `-SSE`, and `Starfield` to `-SF1`, then normalizes direct executables and simple wrappers into explicit launch commands.

The wrapper owns a SQLite-backed artifact and drilldown layer so large conflict scans can be queried through compact summaries instead of giant dumps.

Real verification uses the project-local MO2 sandbox at `.artifacts/mo2` as the authoritative real verification sandbox.

Later workflow skills and MCP integrations should build on `xedit-cli` rather than replace it.
