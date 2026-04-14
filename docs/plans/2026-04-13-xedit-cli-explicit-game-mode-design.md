# xedit-cli Explicit Game-Mode Launch Design

## Goal

Make `xedit-cli` choose xEdit's game mode through explicit command-line arguments instead of inferring behavior from executable names like `FO4Edit.exe`, `SSEEdit.exe`, or `SF1Edit64.exe`.

## Why This Change

xEdit supports all game modes from compatible executables when launched with an explicit game-mode argument such as `-FO4`, `-TES5`, or `-SF1`.

That is a better agent-facing contract than relying on filename conventions because:

- callers can state intent directly with `--game-mode`
- the CLI can normalize `.exe` and simple `.bat/.cmd` launchers the same way
- support for Starfield, Fallout 4, and Skyrim no longer depends on parsing executable names as the primary control surface

## Scope

This slice only updates launcher and process support.

It includes:

- `doctor env` validation for explicit game-mode launch
- `process launch/status/wait/stop` support for explicit game-mode launch
- real verification against the provided Fallout 4, Skyrim, and Starfield launch paths

It does not include:

- MO2 config discovery
- hardcoded launcher paths
- broader live `conflicts index` support for the added game modes

## Command Contract

### `xedit-cli doctor env`

Require:

- `--launcher-path <path>`
- `--game-mode <mode>`

Behavior:

- validate that the launcher exists
- validate that the launcher is usable for explicit mode launch
- validate the game mode against the supported internal mapping
- when `--xedit-pid` is supplied, validate that the running process is xEdit-backed

### `xedit-cli process launch`

Require:

- `--launcher-path <path>`
- `--game-mode <mode>`

Behavior:

- normalize the launcher into an explicit xEdit command
- append the mapped xEdit mode argument
- return the real xEdit PID

### `xedit-cli process status`

Continue to use `--xedit-pid <pid>`.

### `xedit-cli process wait`

Continue to use `--xedit-pid <pid>`.

### `xedit-cli process stop`

Continue to use `--xedit-pid <pid>`.

## Internal Game-Mode Mapping

The CLI should use an internal map from caller-facing game mode to xEdit argument.

Initial required coverage for this slice:

- `Fallout4 -> -FO4`
- `Skyrim -> -TES5`
- `SkyrimSE -> -SSE`
- `Starfield -> -SF1`

The map should be data-driven inside the wrapper and not tied to a specific launcher path.

## Launch Resolution

### Direct `.exe`

Launch the executable directly and append the explicit mode argument.

Example shape:

- `SF1Edit64.exe -SF1`

### Simple `.bat/.cmd` Wrapper

Read the wrapper file and detect whether it is a simple one-command launcher.

For simple wrappers like:

- `hdtTES5EditUTF8_loader.exe FO4Edit.exe`
- `hdtTES5EditUTF8_loader.exe SSEEdit.exe`

Resolve the command relative to the wrapper directory, then launch that normalized command directly with the mapped explicit mode argument.

This avoids depending on `%*` forwarding and keeps behavior consistent across wrappers and direct executables.

### Complex `.bat/.cmd`

If the wrapper is not a simple launch command, fail closed with a compact error telling the caller to provide a direct executable path or a simple wrapper.

## PID Resolution

The process model stays the same:

- capture the pre-launch process set
- launch the normalized command
- find the real xEdit process that appears after launch
- return that PID instead of the shell or helper PID

The CLI should use xEdit metadata plus the explicitly requested game mode as the primary trust signal, not executable-name guessing as the main contract.

## Error Handling

Fail closed for:

- missing `--game-mode`
- unsupported game mode
- unsupported wrapper script shape
- launcher that cannot be normalized to an explicit xEdit command
- launcher that starts but does not produce a real xEdit PID
- PID validation against a non-xEdit process

All failure output should stay compact and operational.

## Verification Strategy

### Automated

- table-driven mode mapping coverage
- `.exe` launch normalization for Starfield-style launchers
- simple `.bat/.cmd` wrapper normalization for Fallout 4 and Skyrim-style launchers
- complex wrapper rejection

### Real Environment

Run launcher/process verification against:

- `B:\WastelandBlues 2.0\Stock Game\Fallout 4\Tools\FO4Edit\runFO4EditCN.bat`
- `C:\softwares\TES Skyrim JL V3\Mod Organizer 2\Stock Game\Skyrim Special Edition\Tools\TES5Edit\runTES5EditCN.bat`
- `D:\SteamLibrary\steamapps\common\Starfield\Tools\xEdit\SF1Edit64.exe`

Cleanup must leave no extra xEdit test instances running.
