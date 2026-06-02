# Plugin Kernel (skeleton — NOT the MO2 plugin)

The plugin kernel is intended to be the in-process MO2 boundary for the
control plane. **Today this directory is a C++ skeleton, not a buildable
MO2 plugin.**

What's actually here:
- `src/Mo2AgentControlPlugin.{h,cpp}` — empty class with a `registry()`
  getter; no MO2 plugin interface (no `getName()`, `init(IOrganizer*)`,
  `createPlugin()` factory).
- `src/CommandRegistry.{h,cpp}` — capability-table skeleton.
- `CMakeLists.txt` — declares a `STATIC` library (`.lib`), NOT a `SHARED`
  library (`.dll`). Building it would not produce a runnable MO2 plugin
  even if all the integration code were filled in.

What IS the MO2 plugin: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`.
It uses `mobase.IPluginGame`-style hooks, exposes a named-pipe IPC server,
and routes `launch.start` through `IOrganizer.startApplication` so the
VFS projects active mods into the spawned process.

If you've followed a "missing `Mo2AgentControl.dll` breaks VFS" thread:
that diagnosis is incorrect. VFS hooking is `usvfs_x{64,86}.dll` (part of
the MO2 install). The Python plugin is what registers the agent-control
named pipe; missing it would prevent IPC, but would not prevent VFS.

This skeleton stays around so the C++ kernel can be implemented later
(e.g., if perf-critical paths need to move out of Python). It is intentionally
unbuilt for v0.1.
