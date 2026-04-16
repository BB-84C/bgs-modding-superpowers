param(
    [string]$BridgeDllPath = $(Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path "tools/xedit-hook-bridge/src/xEditHookBridge.dll")
)

$ErrorActionPreference = "Stop"
$script:TestStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$script:OverallTimeoutSeconds = 90

function Write-TestLog {
    param(
        [string]$Message
    )

    Write-Host ("[module-selection-subset] t+{0:n1}s {1}" -f $script:TestStopwatch.Elapsed.TotalSeconds, $Message)
}

function Assert-WithinOverallTimeout {
    if ($script:TestStopwatch.Elapsed.TotalSeconds -gt $script:OverallTimeoutSeconds) {
        throw "module-selection-subset.integration.ps1 exceeded the overall timeout of $($script:OverallTimeoutSeconds) seconds"
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

function Assert-LineValue {
    param(
        [string]$Content,
        [string]$Key,
        [string]$ExpectedValue,
        [string]$Message
    )

    $pattern = "(?m)^$([regex]::Escape($Key))=$([regex]::Escape($ExpectedValue))\s*$"
    Assert-Match -Value $Content -Pattern $pattern -Message $Message
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

function New-ModuleSelectionSubsetFixture {
    param(
        [string]$TempRoot
    )

    $projectRoot = Join-Path $TempRoot "ModuleSelectionSubsetFixture"
    $cscPath = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe"

    $null = New-Item -ItemType Directory -Path $projectRoot -Force

    if (-not (Test-Path $cscPath -PathType Leaf)) {
        throw "Failed to locate the .NET Framework x86 C# compiler at $cscPath"
    }

    Write-TestLog "Building temporary x86 subset tree-view fixture"

    Set-Content -Path (Join-Path $projectRoot "Program.cs") -Value @'
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
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

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            using (var form = new ModuleSelectionSubsetForm(resultPath))
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

internal sealed class ModuleSelectionSubsetForm : Form
{
    private readonly string _resultPath;
    private readonly NativeModuleTree _moduleTree;
    private readonly System.Windows.Forms.Timer _dependencyTimer;
    private readonly System.Windows.Forms.Timer _timeoutTimer;
    private bool _applyingDependencies;

    internal bool WasConfirmed { get; private set; }

    internal ModuleSelectionSubsetForm(string resultPath)
    {
        _resultPath = resultPath;
        Text = "Module Selection";
        Name = "TfrmModuleSelect";
        Width = 560;
        Height = 360;
        StartPosition = FormStartPosition.CenterScreen;

        _moduleTree = new NativeModuleTree
        {
            Name = "Modules",
            Dock = DockStyle.Fill
        };

        _moduleTree.AddNode("Fallout4.esm", true);
        _moduleTree.AddNode("DLCRobot.esm", true);
        _moduleTree.AddNode("ExamplePatch.esp", true);
        _moduleTree.AddNode("AnotherAddon.esp", true);
        _moduleTree.AddNode("Unrelated.esp", false);

        _moduleTree.CheckedChanged += (_, __) => ApplyDependencies();

        _dependencyTimer = new System.Windows.Forms.Timer { Interval = 50 };
        _dependencyTimer.Tick += (_, __) => ApplyDependencies();

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
            ApplyDependencies();
            WasConfirmed = true;
            Program.WriteResult(_resultPath, "dialog=confirmed");
            Program.WriteResult(_resultPath, "final_selected=" + string.Join("|", GetCheckedNodeNames()));
            Close();
        };

        Controls.Add(_moduleTree);
        Controls.Add(okButton);

        _timeoutTimer = new System.Windows.Forms.Timer { Interval = 12000 };
        _timeoutTimer.Tick += (_, __) =>
        {
            _timeoutTimer.Stop();
            Program.WriteResult(_resultPath, "dialog=timeout");
            Close();
        };

        Shown += (_, __) =>
        {
            _moduleTree.ApplyInitialState();
            ApplyDependencies();
            _dependencyTimer.Start();
            _timeoutTimer.Start();
        };
        FormClosed += (_, __) =>
        {
            _dependencyTimer.Dispose();
            _timeoutTimer.Dispose();
        };
    }

    private IEnumerable<string> GetCheckedNodeNames()
    {
        foreach (var moduleName in _moduleTree.GetNodeNames())
        {
            if (_moduleTree.GetChecked(moduleName))
            {
                yield return moduleName;
            }
        }
    }

    private void ApplyDependencies()
    {
        if (_applyingDependencies)
        {
            return;
        }

        _applyingDependencies = true;
        try
        {
            EnsureRequiredMaster("ExamplePatch.esp", "Fallout4.esm");
            EnsureRequiredMaster("ExamplePatch.esp", "DLCRobot.esm");
            EnsureRequiredMaster("AnotherAddon.esp", "Fallout4.esm");
            PreventIllegalUncheck("Fallout4.esm", "ExamplePatch.esp", "AnotherAddon.esp");
            PreventIllegalUncheck("DLCRobot.esm", "ExamplePatch.esp");
        }
        finally
        {
            _applyingDependencies = false;
        }
    }

    private void EnsureRequiredMaster(string pluginName, string masterName)
    {
        if (_moduleTree.GetChecked(pluginName) && !_moduleTree.GetChecked(masterName))
        {
            _moduleTree.SetChecked(masterName, true);
        }
    }

    private void PreventIllegalUncheck(string masterName, params string[] dependentNames)
    {
        if (_moduleTree.GetChecked(masterName))
        {
            return;
        }

        if (dependentNames.Any(name => _moduleTree.GetChecked(name)))
        {
            _moduleTree.SetChecked(masterName, true);
        }
    }
}

internal sealed class NativeModuleTree : Control
{
    private readonly List<string> _nodeOrder = new List<string>();
    private readonly Dictionary<string, bool> _initialCheckedState = new Dictionary<string, bool>(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, IntPtr> _nodeHandles = new Dictionary<string, IntPtr>(StringComparer.OrdinalIgnoreCase);
    private IntPtr _treeHandle = IntPtr.Zero;
    private bool _raisingChange;
    private bool _initializing;

    internal event EventHandler CheckedChanged;

    internal void AddNode(string moduleName, bool isChecked)
    {
        _nodeOrder.Add(moduleName);
        _initialCheckedState[moduleName] = isChecked;
        if (_treeHandle != IntPtr.Zero)
        {
            InsertNode(moduleName, false);
            SetCheckedCore(moduleName, isChecked, false);
        }
    }

    internal IEnumerable<string> GetNodeNames()
    {
        return _nodeOrder;
    }

    internal bool GetChecked(string moduleName)
    {
        EnsureNodeExists(moduleName);

        var item = new NativeMethods.TVITEM();
        item.mask = NativeMethods.TVIF_STATE;
        item.hItem = _nodeHandles[moduleName];
        item.stateMask = NativeMethods.TVIS_STATEIMAGEMASK;
        if (NativeMethods.SendMessage(_treeHandle, NativeMethods.TVM_GETITEMW, IntPtr.Zero, ref item) == IntPtr.Zero)
        {
            throw new InvalidOperationException("Failed to query native tree checkbox state for " + moduleName);
        }

        var stateImageIndex = (item.state & NativeMethods.TVIS_STATEIMAGEMASK) >> 12;
        return stateImageIndex >= 2;
    }

    internal void SetChecked(string moduleName, bool isChecked)
    {
        SetCheckedCore(moduleName, isChecked, true);
    }

    private void SetCheckedCore(string moduleName, bool isChecked, bool notify)
    {
        EnsureNodeExists(moduleName);

        var item = new NativeMethods.TVITEM();
        item.mask = NativeMethods.TVIF_STATE;
        item.hItem = _nodeHandles[moduleName];
        item.stateMask = NativeMethods.TVIS_STATEIMAGEMASK;
        item.state = isChecked ? NativeMethods.CheckedStateMask : NativeMethods.UncheckedStateMask;
        if (NativeMethods.SendMessage(_treeHandle, NativeMethods.TVM_SETITEMW, IntPtr.Zero, ref item) == IntPtr.Zero)
        {
            throw new InvalidOperationException("Failed to set native tree checkbox state for " + moduleName);
        }

        if (notify)
        {
            OnCheckedChanged();
        }
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);

        CreateNativeTree();
        _initializing = true;
        try
        {
            foreach (var moduleName in _nodeOrder)
            {
                InsertNode(moduleName, false);
            }

            foreach (var moduleName in _nodeOrder)
            {
                SetCheckedCore(moduleName, _initialCheckedState[moduleName], false);
            }
        }
        finally
        {
            _initializing = false;
        }
    }

    internal void ApplyInitialState()
    {
        _initializing = true;
        try
        {
            foreach (var moduleName in _nodeOrder)
            {
                SetCheckedCore(moduleName, _initialCheckedState[moduleName], false);
            }
        }
        finally
        {
            _initializing = false;
        }
    }

    protected override void OnResize(EventArgs e)
    {
        base.OnResize(e);

        if (_treeHandle != IntPtr.Zero)
        {
            NativeMethods.MoveWindow(_treeHandle, 0, 0, Width, Height, true);
        }
    }

    protected override void Dispose(bool disposing)
    {
        if (_treeHandle != IntPtr.Zero)
        {
            NativeMethods.DestroyWindow(_treeHandle);
            _treeHandle = IntPtr.Zero;
        }

        base.Dispose(disposing);
    }

    private void CreateNativeTree()
    {
        var style = NativeMethods.WS_CHILD | NativeMethods.WS_VISIBLE | NativeMethods.WS_TABSTOP | NativeMethods.TVS_CHECKBOXES | NativeMethods.TVS_SHOWSELALWAYS | NativeMethods.TVS_LINESATROOT | NativeMethods.TVS_HASBUTTONS | NativeMethods.TVS_HASLINES;
        _treeHandle = NativeMethods.CreateWindowEx(0, "SysTreeView32", string.Empty, style, 0, 0, Math.Max(Width, 1), Math.Max(Height, 1), Handle, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);
        if (_treeHandle == IntPtr.Zero)
        {
            throw new InvalidOperationException("Failed to create native SysTreeView32 control.");
        }
    }

    private void InsertNode(string moduleName, bool isChecked)
    {
        var insert = new NativeMethods.TVINSERTSTRUCT();
        insert.hParent = IntPtr.Zero;
        insert.hInsertAfter = NativeMethods.TVI_LAST;
        insert.item.mask = NativeMethods.TVIF_TEXT | NativeMethods.TVIF_STATE;
        insert.item.pszText = moduleName;
        insert.item.stateMask = NativeMethods.TVIS_STATEIMAGEMASK;
        insert.item.state = isChecked ? NativeMethods.CheckedStateMask : NativeMethods.UncheckedStateMask;

        var itemHandle = NativeMethods.SendMessage(_treeHandle, NativeMethods.TVM_INSERTITEMW, IntPtr.Zero, ref insert);
        if (itemHandle == IntPtr.Zero)
        {
            throw new InvalidOperationException("Failed to insert native tree item for " + moduleName);
        }

        _nodeHandles[moduleName] = itemHandle;
    }

    private void EnsureNodeExists(string moduleName)
    {
        if (!_nodeHandles.ContainsKey(moduleName))
        {
            throw new InvalidOperationException("Missing native tree node: " + moduleName);
        }
    }

    private void OnCheckedChanged()
    {
        if (_raisingChange)
        {
            return;
        }

        if (_initializing)
        {
            return;
        }

        _raisingChange = true;
        try
        {
            var handler = CheckedChanged;
            if (handler != null)
            {
                handler(this, EventArgs.Empty);
            }
        }
        finally
        {
            _raisingChange = false;
        }
    }
}

internal static class NativeMethods
{
    internal const int WS_CHILD = unchecked((int)0x40000000);
    internal const int WS_VISIBLE = 0x10000000;
    internal const int WS_TABSTOP = 0x00010000;
    internal const int TVS_HASBUTTONS = 0x0001;
    internal const int TVS_HASLINES = 0x0002;
    internal const int TVS_LINESATROOT = 0x0004;
    internal const int TVS_SHOWSELALWAYS = 0x0020;
    internal const int TVS_CHECKBOXES = 0x0100;
    internal const uint TVIF_TEXT = 0x0001;
    internal const uint TVIF_STATE = 0x0008;
    internal const uint TVIS_STATEIMAGEMASK = 0xF000;
    internal static readonly uint UncheckedStateMask = 1u << 12;
    internal static readonly uint CheckedStateMask = 2u << 12;
    internal static readonly IntPtr TVI_LAST = new IntPtr(unchecked((int)0xFFFF0002));
    internal const int TVM_INSERTITEMW = 0x1132;
    internal const int TVM_GETITEMW = 0x113E;
    internal const int TVM_SETITEMW = 0x113F;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    internal struct TVITEM
    {
        public uint mask;
        public IntPtr hItem;
        public uint state;
        public uint stateMask;
        public string pszText;
        public int cchTextMax;
        public int iImage;
        public int iSelectedImage;
        public int cChildren;
        public IntPtr lParam;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    internal struct TVINSERTSTRUCT
    {
        public IntPtr hParent;
        public IntPtr hInsertAfter;
        public TVITEM item;
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    internal static extern IntPtr CreateWindowEx(int exStyle, string className, string windowName, int style, int x, int y, int width, int height, IntPtr parentHandle, IntPtr menuHandle, IntPtr instanceHandle, IntPtr param);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool DestroyWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool MoveWindow(IntPtr hWnd, int x, int y, int nWidth, int nHeight, bool bRepaint);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, ref TVITEM lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, ref TVINSERTSTRUCT lParam);
}
'@

    $fixturePath = Join-Path $projectRoot "FO4Edit.exe"
    $compileOutput = & $cscPath /nologo /target:winexe /platform:x86 /out:$fixturePath /r:System.dll /r:System.Windows.Forms.dll /r:System.Drawing.dll (Join-Path $projectRoot "Program.cs") 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build module-selection subset fixture.`n$($compileOutput -join [Environment]::NewLine)"
    }

    if (-not (Test-Path $fixturePath -PathType Leaf)) {
        throw "Failed to locate fixture executable: $fixturePath"
    }

    return $fixturePath
}

function Invoke-SubsetScenario {
    param(
        [string]$TempRoot,
        [string]$FixturePath,
        [string]$ScenarioName,
        [string]$LoadMode,
        [string[]]$Plugins
    )

    $scenarioRoot = Join-Path $TempRoot $ScenarioName
    $null = New-Item -ItemType Directory -Path $scenarioRoot -Force
    $fixtureResultPath = Join-Path $scenarioRoot "fixture-result.txt"

    $env:XEDIT_CLI_TEST_HOOK_DLL = $BridgeDllPath
    $env:XEDIT_CLI_TEST_FIXTURE_RESULT = $fixtureResultPath

    $arguments = @(
        "process",
        "launch",
        "--launcher-path",
        $FixturePath,
        "--game-mode",
        "Fallout4",
        "--load-mode",
        $LoadMode
    )

    foreach ($plugin in $Plugins) {
        $arguments += @("--plugin", $plugin)
    }

    $launch = Invoke-Cli -Arguments $arguments
    if ($launch.ExitCode -ne 0) {
        throw "xedit-cli process launch failed for $ScenarioName.`n$($launch.Output)"
    }

    $sessionPath = Get-RequiredOutputValue -Output $launch.Output -FieldName "hook-session-path"
    $processId = [int](Get-RequiredOutputValue -Output $launch.Output -FieldName "xedit-pid")
    $statusPath = Join-Path $sessionPath "hook-status.txt"

    Write-TestLog ("Scenario {0} reported pid {1} and session {2}" -f $ScenarioName, $processId, $sessionPath)
    $launchedProcess = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -ne $launchedProcess) {
        Write-TestLog ("Waiting up to 40 seconds for the fixture process to exit in scenario {0}" -f $ScenarioName)
        $null = $launchedProcess.WaitForExit(40000)
        Assert-True -Condition $launchedProcess.HasExited -Message "$ScenarioName fixture should exit after auto-confirm"
    }

    Assert-WithinOverallTimeout
    Assert-True -Condition (Test-Path $fixtureResultPath -PathType Leaf) -Message "$ScenarioName fixture should record final dialog state"
    Assert-True -Condition (Test-Path $statusPath -PathType Leaf) -Message "$ScenarioName hook status should be written"

    return [pscustomobject]@{
        LaunchOutput = $launch.Output
        FixtureResult = Get-Content -Path $fixtureResultPath -Raw
        Status = Get-Content -Path $statusPath -Raw
        StatusPath = $statusPath
        SessionPath = $sessionPath
    }
}

if (-not (Test-Path $BridgeDllPath -PathType Leaf)) {
    throw "Build blocker: missing compiled hook DLL at $BridgeDllPath. Open tools/xedit-hook-bridge/src/xEditHookBridge.dpr in Delphi CE, build Win32 Release, and re-run this test."
}

$tempRoot = Join-Path $env:TEMP ("xedit-cli-module-selection-subset-" + [guid]::NewGuid().ToString("N"))
$null = New-Item -ItemType Directory -Path $tempRoot -Force
$testPassed = $false

$previousHookDll = $env:XEDIT_CLI_TEST_HOOK_DLL
$previousFixtureResult = $env:XEDIT_CLI_TEST_FIXTURE_RESULT

try {
    Write-TestLog "Preparing module-selection subset integration temp workspace"
    Assert-WithinOverallTimeout
    $fixturePath = New-ModuleSelectionSubsetFixture -TempRoot $tempRoot

    Write-TestLog "Running load-mode only scenario"
    Assert-WithinOverallTimeout
    $onlyScenario = Invoke-SubsetScenario -TempRoot $tempRoot -FixturePath $fixturePath -ScenarioName "only" -LoadMode "only" -Plugins @(
        "AnotherAddon.esp",
        "ExamplePatch.esp"
    )

    Assert-Match -Value $onlyScenario.FixtureResult -Pattern '(?m)^dialog=confirmed\s*$' -Message "only scenario should auto-confirm the dialog"
    Assert-LineValue -Content $onlyScenario.FixtureResult -Key "final_selected" -ExpectedValue "Fallout4.esm|DLCRobot.esm|ExamplePatch.esp|AnotherAddon.esp" -Message "only should leave the requested roots selected in module-tree order while keeping required masters"

    Assert-LineValue -Content $onlyScenario.Status -Key "status" -ExpectedValue "module-selection-confirmed" -Message "only scenario should report module-selection-confirmed"
    Assert-LineValue -Content $onlyScenario.Status -Key "load_mode" -ExpectedValue "only" -Message "only scenario should persist load mode"
    Assert-LineValue -Content $onlyScenario.Status -Key "selection_detected" -ExpectedValue "true" -Message "only scenario should report dialog detection"
    Assert-LineValue -Content $onlyScenario.Status -Key "selection_confirmed" -ExpectedValue "true" -Message "only scenario should report confirmed selection"
    Assert-LineValue -Content $onlyScenario.Status -Key "selected_modules" -ExpectedValue "Fallout4.esm|DLCRobot.esm|ExamplePatch.esp|AnotherAddon.esp" -Message "only scenario should capture final selected modules"
    Assert-LineValue -Content $onlyScenario.Status -Key "forced_dependencies" -ExpectedValue "Fallout4.esm|DLCRobot.esm" -Message "only scenario should report masters forced on by dependency rules"

    Write-TestLog "Running load-mode exclude scenario"
    Assert-WithinOverallTimeout
    $excludeScenario = Invoke-SubsetScenario -TempRoot $tempRoot -FixturePath $fixturePath -ScenarioName "exclude" -LoadMode "exclude" -Plugins @(
        "DLCRobot.esm",
        "Unrelated.esp"
    )

    Assert-Match -Value $excludeScenario.FixtureResult -Pattern '(?m)^dialog=confirmed\s*$' -Message "exclude scenario should auto-confirm the dialog"
    Assert-LineValue -Content $excludeScenario.FixtureResult -Key "final_selected" -ExpectedValue "Fallout4.esm|DLCRobot.esm|ExamplePatch.esp|AnotherAddon.esp" -Message "exclude should keep previously unchecked plugins unchecked, clear legal exclusions, and keep blocked exclusions selected"

    Assert-LineValue -Content $excludeScenario.Status -Key "status" -ExpectedValue "module-selection-confirmed" -Message "exclude scenario should report module-selection-confirmed"
    Assert-LineValue -Content $excludeScenario.Status -Key "load_mode" -ExpectedValue "exclude" -Message "exclude scenario should persist load mode"
    Assert-LineValue -Content $excludeScenario.Status -Key "selection_detected" -ExpectedValue "true" -Message "exclude scenario should report dialog detection"
    Assert-LineValue -Content $excludeScenario.Status -Key "selection_confirmed" -ExpectedValue "true" -Message "exclude scenario should report confirmed selection"
    Assert-LineValue -Content $excludeScenario.Status -Key "selected_modules" -ExpectedValue "Fallout4.esm|DLCRobot.esm|ExamplePatch.esp|AnotherAddon.esp" -Message "exclude scenario should capture final selected modules after dependency enforcement"
    Assert-LineValue -Content $excludeScenario.Status -Key "blocked_exclusions" -ExpectedValue "DLCRobot.esm" -Message "exclude scenario should clearly report exclusions blocked by dependency rules"

    if ($excludeScenario.Status -match '(?m)^forced_dependencies=(.+)$') {
        throw "exclude scenario should not report forced_dependencies when the policy is exclude.`nStatus:`n$($excludeScenario.Status)"
    }

    Write-TestLog "Subset integration assertions passed"
    $testPassed = $true
    Write-Host "xedit-cli module-selection subset integration passed."
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
