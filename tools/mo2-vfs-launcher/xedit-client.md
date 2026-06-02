# xedit-client

`xedit-client.ps1` is the MO2-facing outer client for native xEdit automation.

It does not own records, conflicts, jobs, scripts, or patch semantics. Those belong to native xEdit ([BB-84C/TES5Edit](https://github.com/BB-84C/TES5Edit)).

It owns only:

- session-scoped `plugins.txt` generation,
- game-mode and launcher normalization,
- MO2/control-plane launch,
- native serve readiness detection,
- native automation-call request/response artifact handling,
- PID lifecycle.
