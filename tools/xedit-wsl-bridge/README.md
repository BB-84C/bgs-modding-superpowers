# xedit-wsl-bridge

PowerShell scripts that let WSL (Linux) talk to the xEdit automation daemon's
Windows NamedPipe via an HTTP proxy.

## Problem

The xEdit MCP server communicates with the daemon over a Windows NamedPipe
(`\\.\pipe\xedit-<PID>`). WSL processes cannot open Windows NamedPipes directly,
so `curl` from inside WSL cannot reach the daemon.

## Solution

Run `bridge.ps1` on the Windows host. It listens on `http://127.0.0.1:42423`,
accepts HTTP requests, and forwards each one to the NamedPipe.

```
WSL curl  →  127.0.0.1:42423  →  bridge.ps1  →  \\.\pipe\xedit-<PID>  →  xEdit daemon
```

## Files

| File | Purpose |
|---|---|
| `bridge.ps1` | Long-running HTTP→NamedPipe proxy. Listens on port 42423. |
| `query.ps1` | One-shot helper: send a single command to the pipe and print the response. |
| `find_pipe.ps1` | Diagnostic: enumerate Windows named pipes matching `xEdit`/`automation` patterns. |

## Usage

From a **PowerShell** session on the Windows host (with xEdit already running):

```powershell
# Start the bridge (blocks, leave it running)
.\bridge.ps1
```

From **WSL**:

```bash
# Ping
curl --noproxy '*' http://127.0.0.1:42423/system.ping

# Read a record
curl --noproxy '*' 'http://127.0.0.1:42423/records.read?file=Skyrim.esm&formId=0x0003AD8C'

# Call with JSON body
curl --noproxy '*' -X POST http://127.0.0.1:42423/session.save \
  -H 'Content-Type: application/json' -d '{}'
```

## Requirements

- Windows PowerShell 5.1+ (ships with Windows 10/11)
- xEdit automation daemon running with NamedPipe enabled
- WSL2 with `localhost` forwarding enabled (default on modern WSL2)

## Notes

- The bridge binds to `127.0.0.1` only — not exposed to the LAN.
- Each HTTP request opens a fresh pipe connection; the bridge itself is stateless.
- Port 42423 is chosen to avoid conflicts with the daemon's own HTTP listener.
