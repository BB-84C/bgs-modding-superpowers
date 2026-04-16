param(
    [string]$BridgeDllPath = $(Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path "tools/xedit-hook-bridge/src/xEditHookBridge.dll")
)

$ErrorActionPreference = "Stop"
$script:TestStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$script:OverallTimeoutSeconds = 60

function Write-TestLog {
    param(
        [string]$Message
    )

    Write-Host ("[module-selection-all] t+{0:n1}s {1}" -f $script:TestStopwatch.Elapsed.TotalSeconds, $Message)
}

function Assert-WithinOverallTimeout {
    if ($script:TestStopwatch.Elapsed.TotalSeconds -gt $script:OverallTimeoutSeconds) {
        throw "module-selection-all.integration.ps1 exceeded the overall timeout of $($script:OverallTimeoutSeconds) seconds"
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$cliPath = Join-Path $repoRoot "tools/xedit-cli/bin/xedit-cli.ps1"

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Match {
    param(
        [string]$Value,
        [string]$Pattern,
        [string]$Message
    )

    if ($Value -notmatch $Pattern) {
        throw "$Message`nPattern: $Pattern`nActual: $Value"
    }
}

function Invoke-Cli {
    param(
        [string[]]$Arguments
    )

    Write-TestLog ("Invoking xedit-cli: " + ($Arguments -join ' '))

    $stdoutPath = Join-Path $env:TEMP ("xedit-cli-stdout-" + [guid]::NewGuid().ToString("N") + ".txt")
    $stderrPath = Join-Path $env:TEMP ("xedit-cli-stderr-" + [guid]::NewGuid().ToString("N") + ".txt")
    $argumentList = @('-NoProfile', '-File', $cliPath) + $Arguments

    $process = Start-Process -FilePath 'pwsh' -ArgumentList $argumentList -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru

    try {
        $timeoutSeconds = 30
        for ($second = 0; $second -lt $timeoutSeconds; $second++) {
            if ($process.HasExited) {
                break
            }

            Start-Sleep -Seconds 1
            $process.Refresh()

            if (-not $process.HasExited) {
                Write-TestLog ("Still waiting on xedit-cli subprocess ({0}/{1}s)" -f ($second + 1), $timeoutSeconds)
            }
        }

        $process.Refresh()
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            throw "Timed out waiting for xedit-cli command after $timeoutSeconds seconds: $($Arguments -join ' ')"
        }

        $stdout = if (Test-Path $stdoutPath) { Get-Content -Path $stdoutPath -Raw } else { '' }
        $stderr = if (Test-Path $stderrPath) { Get-Content -Path $stderrPath -Raw } else { '' }
        $output = ($stdout + $stderr).Trim()

        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            Output = $output
        }
    }
    finally {
        Remove-Item -Path $stdoutPath -Force -ErrorAction SilentlyContinue
        Remove-Item -Path $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Get-RequiredOutputValue {
    param(
        [string]$Output,
        [string]$FieldName
    )

    $pattern = "(?m)^$([regex]::Escape($FieldName)):\s*(.+)$"
    $match = [regex]::Match($Output, $pattern)
    if (-not $match.Success) {
        throw "Missing CLI output field: $FieldName`nOutput:`n$Output"
    }

    return $match.Groups[1].Value.Trim()
}

function New-ModuleSelectionFixture {
    param(
        [string]$TempRoot
    )

    $projectRoot = Join-Path $TempRoot "ModuleSelectionFixture"
    $cscPath = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe"

    $null = New-Item -ItemType Directory -Path $projectRoot -Force

    if (-not (Test-Path $cscPath -PathType Leaf)) {
        throw "Failed to locate the .NET Framework x86 C# compiler at $cscPath"
    }

    Write-TestLog "Building temporary x86 WinForms fixture"

    Set-Content -Path (Join-Path $projectRoot "Program.cs") -Value @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Reflection;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("FO4Edit")]
[assembly: AssemblyProduct("xEdit")]
[assembly: AssemblyCompany("ElminsterAU")]

internal static class Program
{
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate bool InitDelegate();

    [STAThread]
    private static int Main(string[] args)
    {
        var resultPath = Environment.GetEnvironmentVariable("XEDIT_CLI_TEST_FIXTURE_RESULT");
        var hookDllPath = Environment.GetEnvironmentVariable("XEDIT_CLI_TEST_HOOK_DLL");
        WriteResult(resultPath, "phase=start");
        WriteResult(resultPath, "hook_dll=" + (hookDllPath ?? "<null>"));

        if (string.IsNullOrWhiteSpace(hookDllPath))
        {
            return Fail(resultPath, "missing-hook-dll-path");
        }

        IntPtr module = NativeMethods.LoadLibrary(hookDllPath);
        if (module == IntPtr.Zero)
        {
            return Fail(resultPath, "loadlibrary-failed");
        }

        WriteResult(resultPath, "phase=loadlibrary-ok");

        try
        {
            IntPtr proc = NativeMethods.GetProcAddress(module, "Init");
            if (proc == IntPtr.Zero)
            {
                return Fail(resultPath, "missing-init-export");
            }

            WriteResult(resultPath, "phase=init-export-ok");

            var init = Marshal.GetDelegateForFunctionPointer<InitDelegate>(proc);
            var initResult = init();
            WriteResult(resultPath, "init_result=" + initResult.ToString().ToLowerInvariant());
            if (!initResult)
            {
                return Fail(resultPath, "init-returned-false");
            }

            WriteResult(resultPath, "phase=init-true");

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            using (var form = new ModuleSelectionForm(resultPath))
            {
                Application.Run(form);
                if (form.WasConfirmed)
                {
                    Thread.Sleep(2000);
                }
                return form.WasConfirmed ? 0 : Fail(resultPath, "dialog-not-confirmed");
            }
        }
        catch (Exception ex)
        {
            return Fail(resultPath, "fixture-exception=" + ex.Message);
        }
        finally
        {
            NativeMethods.FreeLibrary(module);
        }
    }

    private static int Fail(string resultPath, string detail)
    {
        WriteResult(resultPath, detail);

        return 1;
    }

    internal static void WriteResult(string resultPath, string detail)
    {
        if (!string.IsNullOrWhiteSpace(resultPath))
        {
            File.AppendAllText(resultPath, detail + Environment.NewLine);
        }
    }

    private static class NativeMethods
    {
        [DllImport("kernel32", SetLastError = true, CharSet = CharSet.Unicode)]
        internal static extern IntPtr LoadLibrary(string lpFileName);

        [DllImport("kernel32", SetLastError = true)]
        internal static extern IntPtr GetProcAddress(IntPtr hModule, string lpProcName);

        [DllImport("kernel32", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static extern bool FreeLibrary(IntPtr hModule);
    }
}

internal sealed class ModuleSelectionForm : Form
{
    private readonly string _resultPath;
    private readonly System.Windows.Forms.Timer _timeoutTimer;

    internal bool WasConfirmed { get; private set; }

    internal ModuleSelectionForm(string resultPath)
    {
        _resultPath = resultPath;
        Text = "Module Selection";
        Name = "TfrmModuleSelect";
        Width = 480;
        Height = 320;
        StartPosition = FormStartPosition.CenterScreen;

        var moduleList = new CheckedListBox
        {
            Name = "Modules",
            Dock = DockStyle.Fill,
            CheckOnClick = true
        };
        moduleList.Items.Add("Fallout4.esm", true);
        moduleList.Items.Add("DLCRobot.esm", true);
        moduleList.Items.Add("ExamplePatch.esp", true);

        var okButton = new Button
        {
            Name = "btnOK",
            Text = "OK",
            Dock = DockStyle.Bottom,
            Height = 32,
            DialogResult = DialogResult.OK
        };
        okButton.Click += (_, __) =>
        {
            WasConfirmed = true;
            WriteResult("dialog=confirmed");
            Close();
        };

        Controls.Add(moduleList);
        Controls.Add(okButton);

        _timeoutTimer = new System.Windows.Forms.Timer { Interval = 10000 };
        _timeoutTimer.Tick += (_, __) =>
        {
            _timeoutTimer.Stop();
            WriteResult("dialog=timeout");
            Close();
        };

        Shown += (_, __) => _timeoutTimer.Start();
        FormClosed += (_, __) => _timeoutTimer.Dispose();
    }

    private void WriteResult(string detail)
    {
        Program.WriteResult(_resultPath, detail);
    }
}
'@

    $fixturePath = Join-Path $projectRoot "FO4Edit.exe"
    $compileOutput = & $cscPath /nologo /target:winexe /platform:x86 /out:$fixturePath /r:System.dll /r:System.Windows.Forms.dll /r:System.Drawing.dll (Join-Path $projectRoot "Program.cs") 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build module-selection fixture.`n$($compileOutput -join [Environment]::NewLine)"
    }

    if (-not (Test-Path $fixturePath -PathType Leaf)) {
        throw "Failed to locate fixture executable: $fixturePath"
    }

    return $fixturePath
}

    if (-not (Test-Path $BridgeDllPath -PathType Leaf)) {
    throw "Build blocker: missing compiled hook DLL at $BridgeDllPath. Open tools/xedit-hook-bridge/src/xEditHookBridge.dpr in Delphi CE, build Win32 Release, and re-run this test."
}

$tempRoot = Join-Path $env:TEMP ("xedit-cli-module-selection-all-" + [guid]::NewGuid().ToString("N"))
$null = New-Item -ItemType Directory -Path $tempRoot -Force
$testPassed = $false

$previousHookDll = $env:XEDIT_CLI_TEST_HOOK_DLL
$previousFixtureResult = $env:XEDIT_CLI_TEST_FIXTURE_RESULT

try {
    Write-TestLog "Preparing module-selection integration temp workspace"
    Assert-WithinOverallTimeout
    $fixturePath = New-ModuleSelectionFixture -TempRoot $tempRoot
    $fixtureResultPath = Join-Path $tempRoot "fixture-result.txt"

    $env:XEDIT_CLI_TEST_HOOK_DLL = $BridgeDllPath
    $env:XEDIT_CLI_TEST_FIXTURE_RESULT = $fixtureResultPath

    Write-TestLog "Launching fixture through xedit-cli process launch"
    Assert-WithinOverallTimeout
    $launch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $fixturePath,
        "--game-mode",
        "Fallout4",
        "--load-mode",
        "all"
    )

    if ($launch.ExitCode -ne 0) {
        throw "xedit-cli process launch failed.`n$($launch.Output)"
    }

    $sessionPath = Get-RequiredOutputValue -Output $launch.Output -FieldName "hook-session-path"
    $processId = [int](Get-RequiredOutputValue -Output $launch.Output -FieldName "xedit-pid")
    $statusPath = Join-Path $sessionPath "hook-status.txt"

    Write-TestLog ("xedit-cli reported pid {0} and session {1}" -f $processId, $sessionPath)
    $launchedProcess = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -ne $launchedProcess) {
        Write-TestLog "Waiting up to 40 seconds for the fixture process to exit"
        $null = $launchedProcess.WaitForExit(40000)
        Assert-True -Condition $launchedProcess.HasExited -Message "module-selection fixture should exit after auto-confirm"
    }

    Write-TestLog "Reading fixture and hook status files"
    Assert-WithinOverallTimeout
    Assert-True -Condition (Test-Path $fixtureResultPath -PathType Leaf) -Message "fixture should record whether the Module Selection dialog was confirmed"
    $fixtureResult = Get-Content -Path $fixtureResultPath -Raw
    Assert-Match -Value $fixtureResult -Pattern '(?m)^dialog=confirmed\s*$' -Message "fixture should report that the dialog was auto-confirmed"

    Assert-True -Condition (Test-Path $statusPath -PathType Leaf) -Message "hook bridge should report status back through the hook session path"
    $status = Get-Content -Path $statusPath -Raw

    Assert-Match -Value $status -Pattern '(?m)^load_mode=all\s*$' -Message "hook bridge should persist the all-mode selection policy"
    Assert-Match -Value $status -Pattern '(?m)^selection_detected=true\s*$' -Message "hook bridge should report Module Selection detection"
    Assert-Match -Value $status -Pattern '(?m)^selection_method=button-click\s*$' -Message "hook bridge should report the explicit confirmation method used"

    if ($status -match '(?m)^status=module-selection-confirmed\s*$') {
        Assert-Match -Value $status -Pattern '(?m)^selection_confirmed=true\s*$' -Message "hook bridge should report a confirmed selection when the terminal success state is written"
    }
    else {
        Assert-Match -Value $status -Pattern '(?m)^status=loaded\s*$' -Message "hook bridge should either write terminal success or preserve the in-flight loaded status for the fast fixture"
        Assert-Match -Value $status -Pattern '(?m)^selection_confirmed=false\s*$' -Message "the in-flight loaded status should not claim confirmation before the terminal success state is written"
    }

    Write-TestLog "Integration assertions passed"
    $testPassed = $true
    Write-Host "xedit-cli module-selection all integration passed."
}
finally {
    Write-TestLog "Cleaning up temp fixture processes and environment"
    Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "$tempRoot*\FO4Edit.exe" } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

    if ($null -eq $previousHookDll) {
        Remove-Item Env:XEDIT_CLI_TEST_HOOK_DLL -ErrorAction SilentlyContinue
    }
    else {
        $env:XEDIT_CLI_TEST_HOOK_DLL = $previousHookDll
    }

    if ($null -eq $previousFixtureResult) {
        Remove-Item Env:XEDIT_CLI_TEST_FIXTURE_RESULT -ErrorAction SilentlyContinue
    }
    else {
        $env:XEDIT_CLI_TEST_FIXTURE_RESULT = $previousFixtureResult
    }

    if ($testPassed -and (Test-Path $tempRoot)) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }
    elseif (Test-Path $tempRoot) {
        Write-TestLog ("Preserving failed temp workspace at {0}" -f $tempRoot)
    }
}

exit 0
