unit HookMain;

interface

function Init(LogLevel: Integer; ProfileName: PWideChar): LongBool; cdecl;

implementation

uses
  Windows,
  Messages,
  CommCtrl,
  Classes,
  SysUtils,
  TlHelp32,
  HookSession,
  HookStatus;

const
  ModuleSelectionCaption = 'Module Selection';
  ModuleSelectionCaptionCompact = 'ModuleSelection';
  ModuleSelectionPollIntervalMs = 250;
  ModuleSelectionTimeoutMs = 30000;
  ModuleSelectionCloseWaitMs = 1500;

type
  PWindowHandle = ^HWND;

  TModuleNode = record
    Handle: HTREEITEM;
    Name: string;
    Checked: Boolean;
  end;

  TModuleNodeArray = array of TModuleNode;

var
  GSession: THookSession;
  GModuleSelectionStartedTick: DWORD = 0;
  GSelectionDetected: LongBool = False;
  GSelectionAttempted: LongBool = False;
  GSelectionMethod: string = '';
  GLastHeartbeatTick: DWORD = 0;
  GSelectionCompleted: LongBool = False;
  GWorkerLoopCount: Integer = 0;
  GSelectedModules: string = '';
  GForcedDependencies: string = '';
  GBlockedExclusions: string = '';

function GetWindowTextValue(const WindowHandle: HWND): string;
var
  TextLength: Integer;
begin
  TextLength := GetWindowTextLength(WindowHandle);
  if TextLength <= 0 then
  begin
    Result := '';
    Exit;
  end;

  SetLength(Result, TextLength + 1);
  GetWindowText(WindowHandle, PChar(Result), TextLength + 1);
  SetLength(Result, StrLen(PChar(Result)));
end;

function GetWindowClassNameValue(const WindowHandle: HWND): string;
var
  Buffer: array[0..255] of Char;
  LengthWritten: Integer;
begin
  LengthWritten := GetClassName(WindowHandle, Buffer, Length(Buffer));
  if LengthWritten > 0 then
    Result := Copy(string(Buffer), 1, LengthWritten)
  else
    Result := '';
end;

procedure WriteWorkerHeartbeat;
begin
  WriteModuleSelectionStatus(
    GSession,
    'loaded',
    'Module Selection worker heartbeat.',
    GSelectionDetected,
    False,
    GSelectionMethod,
    GSelectedModules,
    GForcedDependencies,
    GBlockedExclusions
  );
end;

procedure WriteWorkerCheckpoint(const Detail: string);
begin
  WriteModuleSelectionStatus(
    GSession,
    'loaded',
    Detail,
    GSelectionDetected,
    False,
    GSelectionMethod,
    GSelectedModules,
    GForcedDependencies,
    GBlockedExclusions
  );
end;

function FindChildWindowByClass(const ParentHandle: HWND; const ClassName: string): HWND;
var
  ChildHandle: HWND;
  ChildClassName: string;
  NestedHandle: HWND;
begin
  Result := 0;
  ChildHandle := FindWindowEx(ParentHandle, 0, nil, nil);
  while ChildHandle <> 0 do
  begin
    ChildClassName := GetWindowClassNameValue(ChildHandle);
    if SameText(ChildClassName, ClassName) then
    begin
      Result := ChildHandle;
      Exit;
    end;

    NestedHandle := FindChildWindowByClass(ChildHandle, ClassName);
    if NestedHandle <> 0 then
    begin
      Result := NestedHandle;
      Exit;
    end;

    ChildHandle := FindWindowEx(ParentHandle, ChildHandle, nil, nil);
  end;
end;

function GetStateImageMask(const Checked: Boolean): UINT;
begin
  if Checked then
    Result := UINT(2 shl 12)
  else
    Result := UINT(1 shl 12);
end;

function GetTreeItemText(const TreeHandle: HWND; const ItemHandle: HTREEITEM): string;
var
  Item: TTVItem;
  Buffer: array[0..MAX_PATH] of Char;
begin
  FillChar(Item, SizeOf(Item), 0);
  FillChar(Buffer, SizeOf(Buffer), 0);
  Item.mask := TVIF_TEXT;
  Item.hItem := ItemHandle;
  Item.pszText := Buffer;
  Item.cchTextMax := Length(Buffer);
  if SendMessage(TreeHandle, TVM_GETITEM, 0, LPARAM(@Item)) <> 0 then
    Result := string(Buffer)
  else
    Result := '';
end;

function GetTreeItemChecked(const TreeHandle: HWND; const ItemHandle: HTREEITEM): Boolean;
var
  Item: TTVItem;
  StateImageIndex: UINT;
begin
  FillChar(Item, SizeOf(Item), 0);
  Item.mask := TVIF_STATE;
  Item.hItem := ItemHandle;
  Item.stateMask := TVIS_STATEIMAGEMASK;
  if SendMessage(TreeHandle, TVM_GETITEM, 0, LPARAM(@Item)) = 0 then
  begin
    Result := False;
    Exit;
  end;

  StateImageIndex := (Item.state and TVIS_STATEIMAGEMASK) shr 12;
  Result := StateImageIndex >= 2;
end;

function SetTreeItemChecked(const TreeHandle: HWND; const ItemHandle: HTREEITEM; const Checked: Boolean): Boolean;
var
  Item: TTVItem;
begin
  FillChar(Item, SizeOf(Item), 0);
  Item.mask := TVIF_STATE;
  Item.hItem := ItemHandle;
  Item.stateMask := TVIS_STATEIMAGEMASK;
  Item.state := GetStateImageMask(Checked);
  Result := SendMessage(TreeHandle, TVM_SETITEM, 0, LPARAM(@Item)) <> 0;
end;

procedure AppendModuleNode(var Nodes: TModuleNodeArray; const ItemHandle: HTREEITEM; const ItemName: string; const ItemChecked: Boolean);
var
  NodeIndex: Integer;
begin
  NodeIndex := Length(Nodes);
  SetLength(Nodes, NodeIndex + 1);
  Nodes[NodeIndex].Handle := ItemHandle;
  Nodes[NodeIndex].Name := ItemName;
  Nodes[NodeIndex].Checked := ItemChecked;
end;

procedure CollectTreeNodes(const TreeHandle: HWND; const ItemHandle: HTREEITEM; var Nodes: TModuleNodeArray);
var
  CurrentHandle: HTREEITEM;
  ChildHandle: HTREEITEM;
begin
  CurrentHandle := ItemHandle;
  while CurrentHandle <> nil do
  begin
    AppendModuleNode(Nodes, CurrentHandle, Trim(GetTreeItemText(TreeHandle, CurrentHandle)), GetTreeItemChecked(TreeHandle, CurrentHandle));
    ChildHandle := HTREEITEM(SendMessage(TreeHandle, TVM_GETNEXTITEM, TVGN_CHILD, LPARAM(CurrentHandle)));
    if ChildHandle <> nil then
      CollectTreeNodes(TreeHandle, ChildHandle, Nodes);
    CurrentHandle := HTREEITEM(SendMessage(TreeHandle, TVM_GETNEXTITEM, TVGN_NEXT, LPARAM(CurrentHandle)));
  end;
end;

function ReadVisibleModuleNodes(const TreeHandle: HWND): TModuleNodeArray;
var
  RootHandle: HTREEITEM;
begin
  SetLength(Result, 0);
  RootHandle := HTREEITEM(SendMessage(TreeHandle, TVM_GETNEXTITEM, TVGN_ROOT, 0));
  if RootHandle <> nil then
    CollectTreeNodes(TreeHandle, RootHandle, Result);
end;

function NewModuleNameList: TStringList;
begin
  Result := TStringList.Create;
  Result.CaseSensitive := False;
  Result.Sorted := False;
  Result.Duplicates := dupIgnore;
  Result.StrictDelimiter := True;
  Result.Delimiter := '|';
end;

function ParseRequestedPlugins(const Session: THookSession): TStringList;
var
  RawPlugins: TStringList;
  PluginIndex: Integer;
  PluginName: string;
begin
  Result := NewModuleNameList;
  if Trim(Session.Plugins) = '' then
    Exit;

  RawPlugins := TStringList.Create;
  try
    RawPlugins.StrictDelimiter := True;
    RawPlugins.Delimiter := '|';
    RawPlugins.DelimitedText := Session.Plugins;
    for PluginIndex := 0 to RawPlugins.Count - 1 do
    begin
      PluginName := Trim(RawPlugins[PluginIndex]);
      if PluginName <> '' then
        Result.Add(PluginName);
    end;
  finally
    RawPlugins.Free;
  end;
end;

function JoinModuleNames(const ModuleNames: TStrings): string;
var
  NameIndex: Integer;
begin
  Result := '';
  for NameIndex := 0 to ModuleNames.Count - 1 do
  begin
    if Result <> '' then
      Result := Result + '|';
    Result := Result + ModuleNames[NameIndex];
  end;
end;

function BuildSelectedModules(const Nodes: TModuleNodeArray): string;
var
  SelectedNames: TStringList;
  NodeIndex: Integer;
begin
  SelectedNames := NewModuleNameList;
  try
    for NodeIndex := 0 to Length(Nodes) - 1 do
      if Nodes[NodeIndex].Checked and (Nodes[NodeIndex].Name <> '') then
        SelectedNames.Add(Nodes[NodeIndex].Name);
    Result := JoinModuleNames(SelectedNames);
  finally
    SelectedNames.Free;
  end;
end;

function ReadStableVisibleModuleNodes(const TreeHandle: HWND): TModuleNodeArray;
var
  Attempt: Integer;
begin
  for Attempt := 1 to 5 do
  begin
    Result := ReadVisibleModuleNodes(TreeHandle);
    if (Length(Result) = 0) or (BuildSelectedModules(Result) <> '') or (Attempt = 5) then
      Exit;

    Sleep(200);
  end;
end;

function BuildForcedDependencies(const RequestedPlugins: TStrings; const Nodes: TModuleNodeArray): string;
var
  ForcedNames: TStringList;
  NodeIndex: Integer;
begin
  ForcedNames := NewModuleNameList;
  try
    for NodeIndex := 0 to Length(Nodes) - 1 do
      if Nodes[NodeIndex].Checked and (Nodes[NodeIndex].Name <> '') and (RequestedPlugins.IndexOf(Nodes[NodeIndex].Name) < 0) then
        ForcedNames.Add(Nodes[NodeIndex].Name);
    Result := JoinModuleNames(ForcedNames);
  finally
    ForcedNames.Free;
  end;
end;

function BuildBlockedExclusions(const RequestedPlugins: TStrings; const Nodes: TModuleNodeArray): string;
var
  BlockedNames: TStringList;
  NodeIndex: Integer;
begin
  BlockedNames := NewModuleNameList;
  try
    for NodeIndex := 0 to Length(Nodes) - 1 do
      if Nodes[NodeIndex].Checked and (Nodes[NodeIndex].Name <> '') and (RequestedPlugins.IndexOf(Nodes[NodeIndex].Name) >= 0) then
        BlockedNames.Add(Nodes[NodeIndex].Name);
    Result := JoinModuleNames(BlockedNames);
  finally
    BlockedNames.Free;
  end;
end;

procedure ApplyOnlyPolicy(const TreeHandle: HWND; const RequestedPlugins: TStrings; const Nodes: TModuleNodeArray);
var
  NodeIndex: Integer;
begin
  for NodeIndex := 0 to Length(Nodes) - 1 do
    if Nodes[NodeIndex].Name <> '' then
      SetTreeItemChecked(TreeHandle, Nodes[NodeIndex].Handle, RequestedPlugins.IndexOf(Nodes[NodeIndex].Name) >= 0);
end;

procedure ApplyExcludePolicy(const TreeHandle: HWND; const RequestedPlugins: TStrings; const Nodes: TModuleNodeArray);
var
  NodeIndex: Integer;
begin
  for NodeIndex := 0 to Length(Nodes) - 1 do
    if Nodes[NodeIndex].Name <> '' then
      SetTreeItemChecked(
        TreeHandle,
        Nodes[NodeIndex].Handle,
        Nodes[NodeIndex].Checked and (RequestedPlugins.IndexOf(Nodes[NodeIndex].Name) < 0)
      );
end;

function ApplySubsetPolicyAndCapture(const WindowHandle: HWND; const Session: THookSession; out SelectedModules: string; out ForcedDependencies: string; out BlockedExclusions: string; out Detail: string): Boolean;
var
  TreeHandle: HWND;
  RequestedPlugins: TStringList;
  InitialNodes: TModuleNodeArray;
  FinalNodes: TModuleNodeArray;
begin
  Result := False;
  SelectedModules := '';
  ForcedDependencies := '';
  BlockedExclusions := '';
  Detail := '';

  TreeHandle := FindChildWindowByClass(WindowHandle, 'SysTreeView32');
  if TreeHandle = 0 then
  begin
    Detail := 'Detected Module Selection but could not find the visible module tree.';
    Exit;
  end;

  RequestedPlugins := ParseRequestedPlugins(Session);
  try
    InitialNodes := ReadStableVisibleModuleNodes(TreeHandle);
    if IsOnlyLoadMode(Session) then
      ApplyOnlyPolicy(TreeHandle, RequestedPlugins, InitialNodes)
    else if IsExcludeLoadMode(Session) then
      ApplyExcludePolicy(TreeHandle, RequestedPlugins, InitialNodes)
    else
    begin
      Detail := 'Subset policy requested an unsupported load mode: ' + Session.LoadMode;
      Exit;
    end;

    Sleep(200);
    FinalNodes := ReadVisibleModuleNodes(TreeHandle);
    SelectedModules := BuildSelectedModules(FinalNodes);

    if IsOnlyLoadMode(Session) then
      ForcedDependencies := BuildForcedDependencies(RequestedPlugins, FinalNodes)
    else if IsExcludeLoadMode(Session) then
      BlockedExclusions := BuildBlockedExclusions(RequestedPlugins, FinalNodes);

    if IsOnlyLoadMode(Session) then
      Detail := 'Applied load mode only against the visible module tree and captured the final selection.'
    else
      Detail := 'Applied load mode exclude against the visible module tree and captured the final selection.';

    Result := True;
  finally
    RequestedPlugins.Free;
  end;
end;

function EnumModuleSelectionWindowProc(WindowHandle: HWND; Parameter: LPARAM): BOOL; stdcall;
var
  Caption: string;
begin
  Caption := Trim(GetWindowTextValue(WindowHandle));
  if SameText(Caption, ModuleSelectionCaption) or SameText(Caption, ModuleSelectionCaptionCompact) then
  begin
    PWindowHandle(Parameter)^ := WindowHandle;
    Result := False;
    Exit;
  end;

  Result := True;
end;

procedure EnumCurrentProcessWindowsForModuleSelection(ResultHandle: PWindowHandle);
var
  Snapshot: THandle;
  ThreadEntry: TThreadEntry32;
begin
  Snapshot := CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
  if Snapshot = INVALID_HANDLE_VALUE then
    Exit;

  try
    ThreadEntry.dwSize := SizeOf(ThreadEntry);
    if not Thread32First(Snapshot, ThreadEntry) then
      Exit;

    repeat
      if ThreadEntry.th32OwnerProcessID = GetCurrentProcessId then
      begin
        if not EnumThreadWindows(ThreadEntry.th32ThreadID, @EnumModuleSelectionWindowProc, LPARAM(ResultHandle)) then
          Exit;
      end;
      ThreadEntry.dwSize := SizeOf(ThreadEntry);
    until not Thread32Next(Snapshot, ThreadEntry);
  finally
    CloseHandle(Snapshot);
  end;
end;

function FindModuleSelectionWindow: HWND;
begin
  Result := 0;
  EnumCurrentProcessWindowsForModuleSelection(@Result);
end;

function FindOkButton(const WindowHandle: HWND): HWND;
var
  ChildWindow: HWND;
  Caption: string;
begin
  Result := GetDlgItem(WindowHandle, IDOK);
  if Result <> 0 then
    Exit;

  ChildWindow := FindWindowEx(WindowHandle, 0, nil, nil);
  while ChildWindow <> 0 do
  begin
    Caption := Trim(GetWindowTextValue(ChildWindow));
    if SameText(Caption, 'OK') then
    begin
      Result := ChildWindow;
      Exit;
    end;
    ChildWindow := FindWindowEx(WindowHandle, ChildWindow, nil, nil);
  end;

  Result := 0;
end;

function TryConfirmModuleSelection(const WindowHandle: HWND; out Method: string): Boolean;
var
  OkButton: HWND;
begin
  Method := '';
  OkButton := FindOkButton(WindowHandle);
  if OkButton <> 0 then
  begin
    PostMessage(OkButton, BM_CLICK, 0, 0);
    Method := 'button-click';
    Result := True;
    Exit;
  end;

  SendMessage(WindowHandle, WM_COMMAND, IDOK, 0);
  Method := 'wm-command';
  PostMessage(WindowHandle, WM_KEYDOWN, VK_RETURN, 0);
  PostMessage(WindowHandle, WM_KEYUP, VK_RETURN, 0);
  Result := True;
end;

function WaitForModuleSelectionClose(const OriginalWindowHandle: HWND; const TimeoutMs: DWORD): Boolean;
var
  WaitStartedTick: DWORD;
begin
  WaitStartedTick := GetTickCount;
  repeat
    if (OriginalWindowHandle = 0) or (not IsWindow(OriginalWindowHandle)) then
    begin
      Result := True;
      Exit;
    end;

    Sleep(50);
  until GetTickCount - WaitStartedTick >= TimeoutMs;

  Result := False;
end;

procedure CompleteModuleSelection(const Status: string; const Detail: string; const SelectionDetected: LongBool; const SelectionConfirmed: LongBool);
begin
  GSelectionCompleted := True;
  WriteModuleSelectionStatus(GSession, Status, Detail, SelectionDetected, SelectionConfirmed, GSelectionMethod, GSelectedModules, GForcedDependencies, GBlockedExclusions);
end;

function ModuleSelectionWorkerProc(Parameter: Pointer): Integer;
var
  ModuleSelectionWindow: HWND;
  ConfirmationMethod: string;
  PolicyDetail: string;
begin
  Result := 0;
  try
    WriteModuleSelectionStatus(GSession, 'loaded', 'Module Selection worker thread started.', False, False, '', '', '', '');
    GLastHeartbeatTick := GModuleSelectionStartedTick;
    GWorkerLoopCount := 0;

    while GetTickCount - GModuleSelectionStartedTick < ModuleSelectionTimeoutMs do
    begin
      Inc(GWorkerLoopCount);

      if GetTickCount - GLastHeartbeatTick >= 2000 then
      begin
        GLastHeartbeatTick := GetTickCount;
        if not GSelectionCompleted then
          WriteWorkerHeartbeat;
      end;

      if (GWorkerLoopCount <= 3) and not GSelectionCompleted then
        WriteWorkerCheckpoint('Worker loop ' + IntToStr(GWorkerLoopCount) + ' before window search.');

      ModuleSelectionWindow := FindModuleSelectionWindow;

      if (GWorkerLoopCount <= 3) and not GSelectionCompleted then
        WriteWorkerCheckpoint('Worker loop ' + IntToStr(GWorkerLoopCount) + ' after window search. WindowHandle=' + IntToHex(ModuleSelectionWindow, 8));

      if ModuleSelectionWindow = 0 then
      begin
        if GSelectionDetected and GSelectionAttempted then
        begin
          CompleteModuleSelection('module-selection-confirmed', 'Detected Module Selection and confirmed the requested selection policy.', True, True);
          Exit;
        end;

        Sleep(ModuleSelectionPollIntervalMs);
        Continue;
      end;

      GSelectionDetected := True;

      if not GSelectionAttempted then
      begin
        if UsesSubsetLoadMode(GSession) then
        begin
          if not ApplySubsetPolicyAndCapture(ModuleSelectionWindow, GSession, GSelectedModules, GForcedDependencies, GBlockedExclusions, PolicyDetail) then
          begin
            CompleteModuleSelection('failed', PolicyDetail, True, False);
            Exit;
          end;
        end;

        if not TryConfirmModuleSelection(ModuleSelectionWindow, ConfirmationMethod) then
        begin
          CompleteModuleSelection('failed', 'Detected Module Selection but could not trigger confirmation for load mode ' + GSession.LoadMode + '.', True, False);
          Exit;
        end;

        GSelectionAttempted := True;
        GSelectionMethod := ConfirmationMethod;
        if WaitForModuleSelectionClose(ModuleSelectionWindow, ModuleSelectionCloseWaitMs) then
        begin
          CompleteModuleSelection('module-selection-confirmed', 'Detected Module Selection and confirmed the requested selection policy.', True, True);
          Exit;
        end;

        if UsesSubsetLoadMode(GSession) then
          WriteModuleSelectionStatus(GSession, 'loaded', PolicyDetail, True, False, GSelectionMethod, GSelectedModules, GForcedDependencies, GBlockedExclusions)
        else
          WriteModuleSelectionStatus(GSession, 'loaded', 'Detected Module Selection and triggered confirmation for load mode all.', True, False, GSelectionMethod, '', '', '');
      end;

      Sleep(ModuleSelectionPollIntervalMs);
    end;

    if GSelectionDetected and GSelectionAttempted then
    begin
      CompleteModuleSelection('failed', 'Detected Module Selection but it did not close after confirmation was attempted for load mode ' + GSession.LoadMode + '.', True, False);
    end
    else
    begin
      CompleteModuleSelection('failed', 'Timed out waiting for Module Selection while load mode ' + GSession.LoadMode + ' was active.', False, False);
    end;
  except
    on E: Exception do
      CompleteModuleSelection('failed', 'Module Selection worker failed: ' + E.Message, GSelectionDetected, False);
  end;
end;

function Init(LogLevel: Integer; ProfileName: PWideChar): LongBool; cdecl;
var
  Session: THookSession;
  ValidationMessage: string;
  WorkerThreadHandle: THandle;
  WorkerThreadId: DWORD;
begin
  if (LogLevel <> 0) and (ProfileName <> nil) then
  begin
    // The real xEdit hook contract passes log level and MO profile name.
  end;

  Session := ReadHookSession;
  ValidationMessage := DescribeHookSessionValidation(Session);

  if ValidationMessage <> '' then
  begin
    WriteLoadStatus(Session, 'failed', ValidationMessage);
    Result := False;
    Exit;
  end;

  try
    if not IsAllLoadMode(Session) then
    begin
      if not UsesSubsetLoadMode(Session) then
      begin
        WriteLoadStatus(Session, 'loaded', 'Init completed. Module Selection automation is only implemented for load modes all, only, and exclude in this slice.');
        Result := True;
        Exit;
      end;

      if Trim(Session.Plugins) = '' then
      begin
        WriteLoadStatus(Session, 'failed', 'Subset load modes require XEDIT_CLI_HOOK_PLUGINS.');
        Result := False;
        Exit;
      end;
    end;

    GSession := Session;
    GModuleSelectionStartedTick := GetTickCount;
    GSelectionDetected := False;
    GSelectionAttempted := False;
    GSelectionMethod := '';
    GSelectionCompleted := False;
    GWorkerLoopCount := 0;
    GSelectedModules := '';
    GForcedDependencies := '';
    GBlockedExclusions := '';
    WorkerThreadId := 0;
    WorkerThreadHandle := BeginThread(nil, 0, ModuleSelectionWorkerProc, nil, 0, WorkerThreadId);
    if WorkerThreadHandle = 0 then
      raise Exception.Create('Failed to start Module Selection worker thread.');
    CloseHandle(WorkerThreadHandle);

    if IsAllLoadMode(Session) then
      WriteModuleSelectionStatus(Session, 'loaded', 'Init completed. Waiting to confirm the current Module Selection for load mode all.', False, False, '', '', '', '')
    else
      WriteModuleSelectionStatus(Session, 'loaded', 'Init completed. Waiting to apply the requested subset policy when Module Selection appears.', False, False, '', '', '', '');

    Result := True;
  except
    on E: Exception do
    begin
      WriteLoadStatus(Session, 'failed', E.Message);
      Result := False;
    end;
  end;
end;

end.
