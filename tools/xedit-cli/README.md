# xedit-cli

This directory is reserved for the primary public wrapper that orchestrates upstream xEdit through wrapper-owned Pascal scripts.

The wrapper should keep xEdit external and treat it as the execution engine.

Phase 1 is a safe, read-only workflow focused on conflict indexing and record inspection.

The current slice now accepts a caller-provided launcher path for `doctor env`, validates an optional xEdit PID, and implements PID-based process lifecycle commands, while the broader live-run orchestration remains the production-launch target contract instead of assuming a manually opened session.

The approved step-1 target contract adds a step-1 hook bridge for Module Selection so the wrapper can keep xEdit external while still automating the first dialog. It defines `--load-mode all|only|exclude`: `all` forbids `--plugin`, while `only` and `exclude` require at least one repeatable `--plugin` argument. The caller chooses a subset, but the MO2-backed active list remains the source of truth for full plugin order, so plugin names must match that active set and subset results preserve MO2 order.

The same target contract uses a no-fork `hook.dll` bridge through the existing MO seam. The bridge is intended to confirm the current MO2-backed selection for `all`, apply requested roots for `only`, and apply requested removals for `exclude` without redefining global load order inside the CLI. For real hook-enabled launches, `process launch` also accepts `--mo-profile <name>`, appends `-moprofile:"<name>"`, and deploys the built bridge DLL to xEdit's expected `..\Mod Organizer\hook.dll` location before launch.

Launcher-driven commands require authoritative `--game-mode`. `--game-mode` is the primary trust and control signal for mode selection, not executable-name-derived guessing. The CLI maps `Fallout4` to `-FO4`, `Skyrim` to `-TES5`, `SkyrimSE` to `-SSE`, and `Starfield` to `-SF1`, then normalizes direct executables and simple wrappers into explicit launch commands.

The wrapper owns a SQLite-backed artifact and drilldown layer so large conflict scans can be queried through compact summaries instead of giant dumps.

Later workflow skills and MCP integrations should build on `xedit-cli` rather than replace it.
