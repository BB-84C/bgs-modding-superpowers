---
id: install-planning.mo2-windows-credential-mining.v1
title: MO2 stores Nexus credentials in Windows Credential Manager (global, per-user DPAPI)
kind: rule
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "MO2's Nexus API key and OAuth tokens are stored GLOBALLY in Windows Credential Manager (not per-MO2-instance, not in ModOrganizer.ini, not in registry); read via Win32 CredReadW with target names `ModOrganizer2_APIKEY` (legacy 162-char key) and `ModOrganizer2_NEXUS_OAUTH_TOKENS` (Compact JSON {access_token, refresh_token, expires_at, scope, token_type})."
  confidence: high
queryKeys: [nexus API key, Windows Credential Manager, ModOrganizer2_APIKEY, NEXUS_OAUTH_TOKENS, CredRead, MO2 nexus auth, mining credentials]
severity: high
sources:
  - kind: tooling-docs
    url: "https://raw.githubusercontent.com/ModOrganizer2/modorganizer/master/src/settings.cpp"
    ref: "MO2 settings.cpp — GlobalSettings::nexusApiKey + setNexusApiKey use getWindowsCredential/setWindowsCredential with NexusLegacyCredentialKey='APIKEY' and NexusOAuthCredentialKey='NEXUS_OAUTH_TOKENS'"
  - kind: tooling-docs
    url: "https://raw.githubusercontent.com/ModOrganizer2/modorganizer/master/src/nxmaccessmanager.cpp"
    ref: "MO2 nxmaccessmanager.cpp — NXMAccessManager constructor loads tokens via GlobalSettings::nexusOAuthTokens / nexusApiKey at startup"
  - kind: official
    url: "https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credreadw"
    ref: "Microsoft Win32 CredReadW API reference"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# MO2 stores Nexus credentials in Windows Credential Manager (global, per-user DPAPI)

MO2's Nexus API key and OAuth tokens are stored globally for the Windows user in Windows Credential Manager, not per MO2 instance. If the user authenticated Nexus in one MO2 install, another MO2 install running as the same Windows account can read the same credentials through the same Windows credential targets. This matters for agents because an apparently unauthenticated test instance may still have usable Nexus credentials available outside `ModOrganizer.ini`.

The credentials are `CRED_TYPE_GENERIC` entries protected by per-user DPAPI. MO2 uses the target names `ModOrganizer2_APIKEY` for the legacy 162-character API key and `ModOrganizer2_NEXUS_OAUTH_TOKENS` for the OAuth token blob. Read them with Win32 `CredReadW`; the `CredentialBlob` is bytes and should be decoded defensively. In practice the blob may be UTF-8 or UTF-16LE, so a nulls-at-odd/even-byte heuristic is safer than assuming one encoding.

Common failure modes are misleading. `cmdkey /list | findstr /i nexus` can miss the legacy key because the target name is `ModOrganizer2_APIKEY`, not a string containing `nexus`. The HKCU registry does not contain the credential payload; only a few cosmetic global flags appear there. `ModOrganizer.ini` also does not store Nexus auth fields in the `Settings` section. Treat the Windows Credential Manager entry as the source of truth.

[CAUTION] Reading user credentials is sensitive real-world state. Do it only with explicit user authorization for the current task, mask values in logs, and recommend rotating the key if any leak risk exists. Verify the key with Nexus' validation endpoint rather than printing it:

```powershell
$target = "ModOrganizer2_APIKEY"
$sig = @"
using System;
using System.Runtime.InteropServices;
public static class CredUtil {
  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
  public struct CREDENTIAL {
    public UInt32 Flags;
    public UInt32 Type;
    public IntPtr TargetName;
    public IntPtr Comment;
    public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
    public UInt32 CredentialBlobSize;
    public IntPtr CredentialBlob;
    public UInt32 Persist;
    public UInt32 AttributeCount;
    public IntPtr Attributes;
    public IntPtr TargetAlias;
    public IntPtr UserName;
  }
  [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  public static extern bool CredReadW(string target, UInt32 type, UInt32 reservedFlag, out IntPtr credentialPtr);
  [DllImport("advapi32.dll", SetLastError = true)]
  public static extern void CredFree(IntPtr buffer);
}
"@
Add-Type $sig

$ptr = [IntPtr]::Zero
if (-not [CredUtil]::CredReadW($target, 1, 0, [ref]$ptr)) { throw "Credential not found: $target" }
try {
  $cred = [Runtime.InteropServices.Marshal]::PtrToStructure($ptr, [type][CredUtil+CREDENTIAL])
  $bytes = New-Object byte[] $cred.CredentialBlobSize
  [Runtime.InteropServices.Marshal]::Copy($cred.CredentialBlob, $bytes, 0, $bytes.Length)
  $looksUtf16 = ($bytes.Length -gt 2) -and (($bytes[1], $bytes[3], $bytes[5] | Where-Object { $_ -eq 0 }).Count -ge 2)
  $value = if ($looksUtf16) { [Text.Encoding]::Unicode.GetString($bytes) } else { [Text.Encoding]::UTF8.GetString($bytes) }
  $masked = if ($value.Length -gt 12) { $value.Substring(0, 6) + "..." + $value.Substring($value.Length - 4) } else { "<short>" }
  "Credential loaded: $masked"
  Invoke-RestMethod -Uri "https://api.nexusmods.com/v1/users/validate.json" -Headers @{ "APIKEY" = $value; "Application-Name" = "bgs-modding-superpowers"; "Application-Version" = "1.0" }
}
finally {
  if ($ptr -ne [IntPtr]::Zero) { [CredUtil]::CredFree($ptr) }
}
```
