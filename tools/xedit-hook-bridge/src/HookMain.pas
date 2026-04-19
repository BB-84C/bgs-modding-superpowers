unit HookMain;

interface

function Init(LogLevel: Integer; ProfileName: PWideChar): LongBool; cdecl;

implementation

uses
  Winapi.Windows,
  Winapi.Messages,
  Winapi.CommCtrl,
  Winapi.ActiveX,
  Winapi.OleAcc,
  System.Classes,
  Vcl.Controls,
  Vcl.Forms,
  System.Rtti,
  System.TypInfo,
  System.SysUtils,
  System.Variants,
  Winapi.TlHelp32,
  HookSession,
  HookStatus;

const
  ModuleSelectionCaption = 'Module Selection';
  ModuleSelectionCaptionCompact = 'ModuleSelection';
  StartupWhatsNewCaptionPrefix = 'What''s New?';
  StartupWhatsNewClassName = 'TfrmRichEdit';
  StartupDeveloperMessageCaptionPrefix = 'A message from the developer';
  StartupDeveloperMessageClassName = 'TfrmDeveloperMessage';
  ModuleSelectionPollIntervalMs = 250;
  ModuleSelectionTimeoutMs = 30000;
  ModuleSelectionCloseWaitMs = 1500;
  MaxDiagnosticChildWindows = 32;
  MaxVirtualTreeTopLevelSampleNodes = 3;

type
  PWindowHandle = ^HWND;

  PWindowSnapshotContext = ^TWindowSnapshotContext;

  TWindowSnapshotContext = record
    Lines: TStringList;
    ChildCount: Integer;
    ChildLogged: Integer;
  end;

  TModuleNode = record
    Handle: HTREEITEM;
    Name: string;
    Checked: Boolean;
  end;

  TModuleNodeArray = array of TModuleNode;

  TModuleTreeKind = (
    mtkNativeTreeView,
    mtkVclVirtualTree
  );

  TModuleTreeAccess = record
    Kind: TModuleTreeKind;
    TreeHandle: HWND;
    TreeComponent: TComponent;
  end;

var
  GSession: THookSession;
  GModuleSelectionStartedTick: DWORD = 0;
  GSelectionDetected: LongBool = False;
  GSelectionAttempted: LongBool = False;
  GLastHeartbeatTick: DWORD = 0;
  GSelectionCompleted: LongBool = False;
  GWorkerLoopCount: Integer = 0;
  GSelectedModules: string = '';
  GSelectionDiagnostics: string = '';

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
    GSelectedModules,
    GSelectionDiagnostics
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
    GSelectedModules,
    GSelectionDiagnostics
  );
end;

function BoolToDiagnosticValue(const Value: Boolean): string;
begin
  if Value then
    Result := 'true'
  else
    Result := 'false';
end;

function FormatDiagnosticText(const Value: string): string;
begin
  Result := Trim(Value);
  Result := StringReplace(Result, #13, ' ', [rfReplaceAll]);
  Result := StringReplace(Result, #10, ' ', [rfReplaceAll]);
end;

function FormatDiagnosticHandle(const WindowHandle: HWND): string;
begin
  Result := '0x' + IntToHex(NativeUInt(WindowHandle), SizeOf(NativeUInt) * 2);
end;

function FormatDiagnosticHResult(const Value: HRESULT): string;
begin
  Result := '0x' + IntToHex(Cardinal(Value), 8);
end;

function FormatDiagnosticRect(const Rect: TRect): string;
begin
  Result :=
    IntToStr(Rect.Left) + ',' +
    IntToStr(Rect.Top) + ',' +
    IntToStr(Rect.Right) + ',' +
    IntToStr(Rect.Bottom) +
    ' ' + IntToStr(Rect.Right - Rect.Left) + 'x' + IntToStr(Rect.Bottom - Rect.Top);
end;

function FormatWindowSnapshotLine(const Prefix: string; const WindowHandle: HWND; const ParentHandle: HWND): string;
var
  WindowRect: TRect;
  WindowClass: string;
  WindowCaption: string;
begin
  FillChar(WindowRect, SizeOf(WindowRect), 0);
  GetWindowRect(WindowHandle, WindowRect);
  WindowClass := FormatDiagnosticText(GetWindowClassNameValue(WindowHandle));
  WindowCaption := FormatDiagnosticText(GetWindowTextValue(WindowHandle));
  Result :=
    Prefix + 'hwnd=' + FormatDiagnosticHandle(WindowHandle) +
    ',parent_hwnd=' + FormatDiagnosticHandle(ParentHandle) +
    ',class=' + WindowClass +
    ',caption=' + WindowCaption +
    ',rect=' + FormatDiagnosticRect(WindowRect) +
     ',visible=' + BoolToDiagnosticValue(IsWindowVisible(WindowHandle)) +
     ',style=0x' + IntToHex(GetWindowLongPtr(WindowHandle, GWL_STYLE), SizeOf(NativeInt) * 2) +
     ',exstyle=0x' + IntToHex(GetWindowLongPtr(WindowHandle, GWL_EXSTYLE), SizeOf(NativeInt) * 2);
end;

function EnumChildWindowSnapshotProc(WindowHandle: HWND; Parameter: LPARAM): BOOL; stdcall;
var
  Context: PWindowSnapshotContext;
begin
  Context := PWindowSnapshotContext(Parameter);
  Inc(Context.ChildCount);
  if Context.ChildLogged < MaxDiagnosticChildWindows then
  begin
    Context.Lines.Add(FormatWindowSnapshotLine('child[' + IntToStr(Context.ChildLogged) + ']=', WindowHandle, GetParent(WindowHandle)));
    Inc(Context.ChildLogged);
  end;
  Result := True;
end;

procedure CaptureModuleSelectionDiagnostics(const WindowHandle: HWND; const VclLines: TStrings);
var
  Lines: TStringList;
  RootRect: TRect;
  SnapshotContext: TWindowSnapshotContext;
  RootCaption: string;
  RootClass: string;
begin
  if not IsWindow(WindowHandle) then
    Exit;

  Lines := TStringList.Create;
  try
    FillChar(RootRect, SizeOf(RootRect), 0);
    GetWindowRect(WindowHandle, RootRect);
    RootCaption := FormatDiagnosticText(GetWindowTextValue(WindowHandle));
    RootClass := FormatDiagnosticText(GetWindowClassNameValue(WindowHandle));

    Lines.Add('root_hwnd=' + FormatDiagnosticHandle(WindowHandle));
    Lines.Add('root_parent_hwnd=' + FormatDiagnosticHandle(GetParent(WindowHandle)));
    Lines.Add('root_caption=' + RootCaption);
    Lines.Add('root_class=' + RootClass);
    Lines.Add('root_rect=' + FormatDiagnosticRect(RootRect));
    Lines.Add('root_visible=' + BoolToDiagnosticValue(IsWindowVisible(WindowHandle)));
    Lines.Add('root_style=0x' + IntToHex(GetWindowLongPtr(WindowHandle, GWL_STYLE), SizeOf(NativeInt) * 2));
    Lines.Add('root_exstyle=0x' + IntToHex(GetWindowLongPtr(WindowHandle, GWL_EXSTYLE), SizeOf(NativeInt) * 2));

    SnapshotContext.Lines := Lines;
    SnapshotContext.ChildCount := 0;
    SnapshotContext.ChildLogged := 0;
    EnumChildWindows(WindowHandle, @EnumChildWindowSnapshotProc, LPARAM(@SnapshotContext));
    Lines.Add('child_count=' + IntToStr(SnapshotContext.ChildCount));
    Lines.Add('child_logged=' + IntToStr(SnapshotContext.ChildLogged));

    if VclLines <> nil then
      Lines.AddStrings(VclLines);

    GSelectionDiagnostics := Lines.Text;
  finally
    Lines.Free;
  end;
end;

procedure AppendModuleSelectionDiagnosticLine(const Line: string);
begin
  if Trim(Line) = '' then
    Exit;

  if GSelectionDiagnostics <> '' then
    GSelectionDiagnostics := GSelectionDiagnostics + sLineBreak;
  GSelectionDiagnostics := GSelectionDiagnostics + Line;
end;

procedure AppendVirtualTreeHwndProbeDiagnostics(const VirtualTreeHandle: HWND; const MaxNodes: Integer); forward;
procedure AppendVirtualTreeTopLevelSampleDiagnostics(const TreeComponent: TObject; const MaxNodes: Integer); forward;

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
    if SameText(ChildClassName, ClassName) or (Pos(LowerCase(ClassName), LowerCase(ChildClassName)) > 0) then
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

function TryInvokeObjectMethod(const Instance: TObject; const MethodName: string; const Args: array of TValue; out Value: TValue): Boolean;
var
  Context: TRttiContext;
  RttiType: TRttiType;
  RttiMethod: TRttiMethod;
begin
  Result := False;
  Value := TValue.Empty;
  if Instance = nil then
    Exit;

  Context := TRttiContext.Create;
  try
    RttiType := Context.GetType(Instance.ClassType);
    if RttiType = nil then
      Exit;

    RttiMethod := RttiType.GetMethod(MethodName);
    if RttiMethod = nil then
      Exit;

    Value := RttiMethod.Invoke(Instance, Args);
    Result := True;
  finally
    Context.Free;
  end;
end;

function TryGetIndexedPropertyValue(const Instance: TObject; const PropertyName: string; const Args: array of TValue; out Value: TValue): Boolean;
var
  Context: TRttiContext;
  RttiType: TRttiType;
  IndexedProperty: TRttiIndexedProperty;
begin
  Result := False;
  Value := TValue.Empty;
  if Instance = nil then
    Exit;

  Context := TRttiContext.Create;
  try
    RttiType := Context.GetType(Instance.ClassType);
    if RttiType = nil then
      Exit;

    IndexedProperty := RttiType.GetIndexedProperty(PropertyName);
    if IndexedProperty = nil then
      Exit;

    Value := IndexedProperty.GetValue(Instance, Args);
    Result := True;
  finally
    Context.Free;
  end;
end;

function TrySetIndexedEnumPropertyOrdinal(const Instance: TObject; const PropertyName: string; const Args: array of TValue; const Ordinal: Integer): Boolean;
var
  Context: TRttiContext;
  RttiType: TRttiType;
  IndexedProperty: TRttiIndexedProperty;
  EnumValue: TValue;
begin
  Result := False;
  if Instance = nil then
    Exit;

  Context := TRttiContext.Create;
  try
    RttiType := Context.GetType(Instance.ClassType);
    if RttiType = nil then
      Exit;

    IndexedProperty := RttiType.GetIndexedProperty(PropertyName);
    if (IndexedProperty = nil) or (IndexedProperty.PropertyType = nil) then
      Exit;

    EnumValue := TValue.FromOrdinal(IndexedProperty.PropertyType.Handle, Ordinal);
    IndexedProperty.SetValue(Instance, Args, EnumValue);
    Result := True;
  finally
    Context.Free;
  end;
end;

function TryResolveModuleSelectionForm(const WindowHandle: HWND; out ModuleForm: TCustomForm; out Detail: string): Boolean;
var
  WindowControl: TWinControl;
  RootHandle: HWND;
  FormIndex: Integer;
  CandidateForm: TCustomForm;
  Diagnostics: TStringList;
  MatchedForm: Boolean;
begin
  Result := False;
  Detail := '';
  ModuleForm := nil;
  Diagnostics := TStringList.Create;
  MatchedForm := False;

  Diagnostics.Add('find_control_window=' + FormatDiagnosticHandle(WindowHandle));

  try
    WindowControl := FindControl(WindowHandle);
    if WindowControl <> nil then
      Diagnostics.Add('find_control=' + WindowControl.ClassName + '.' + WindowControl.Name)
    else
      Diagnostics.Add('find_control=nil');

    if WindowControl is TCustomForm then
    begin
      ModuleForm := TCustomForm(WindowControl);
      Diagnostics.Add('find_control_form=' + ModuleForm.ClassName + '.' + ModuleForm.Name);
    end
    else if WindowControl <> nil then
    begin
      ModuleForm := GetParentForm(WindowControl);
      if ModuleForm <> nil then
        Diagnostics.Add('get_parent_form=' + ModuleForm.ClassName + '.' + ModuleForm.Name)
      else
        Diagnostics.Add('get_parent_form=nil');
    end
    else
      Diagnostics.Add('get_parent_form=skipped');

    if ModuleForm = nil then
    begin
      RootHandle := GetAncestor(WindowHandle, GA_ROOT);
      Diagnostics.Add('root_ancestor=' + FormatDiagnosticHandle(RootHandle));
      Diagnostics.Add('screen_form_count=' + IntToStr(Screen.FormCount));
      for FormIndex := 0 to Screen.FormCount - 1 do
      begin
        CandidateForm := Screen.Forms[FormIndex];
        if CandidateForm <> nil then
          Diagnostics.Add(
            'screen_form[' + IntToStr(FormIndex) + ']=' +
            CandidateForm.ClassName + '.' + CandidateForm.Name +
            ',handle=' + FormatDiagnosticHandle(CandidateForm.Handle)
          );
        if (CandidateForm <> nil) and
           (SameText(CandidateForm.ClassName, 'TfrmModuleSelect') or SameText(CandidateForm.Name, 'TfrmModuleSelect')) and
           ((CandidateForm.Handle = WindowHandle) or (CandidateForm.Handle = RootHandle)) then
        begin
          ModuleForm := CandidateForm;
          MatchedForm := True;
          Break;
        end;
      end;
      if MatchedForm then
        Diagnostics.Add('screen_forms_match=true')
      else
        Diagnostics.Add('screen_forms_match=false');
    end;

    if ModuleForm = nil then
    begin
      Diagnostics.Add('resolved_form=nil');
      CaptureModuleSelectionDiagnostics(WindowHandle, Diagnostics);
      Detail := 'Detected Module Selection but could not find the visible module tree (form not found).';
      Exit;
    end;

    Diagnostics.Add('resolved_form=' + ModuleForm.ClassName + '.' + ModuleForm.Name);

    if not (SameText(ModuleForm.ClassName, 'TfrmModuleSelect') or SameText(ModuleForm.Name, 'TfrmModuleSelect')) then
    begin
      Diagnostics.Add('resolved_form_usable=false');
      CaptureModuleSelectionDiagnostics(WindowHandle, Diagnostics);
      Detail := 'Detected Module Selection but could not find the visible module tree (form not found).';
      ModuleForm := nil;
      Exit;
    end;

    Diagnostics.Add('resolved_form_usable=true');
    CaptureModuleSelectionDiagnostics(WindowHandle, Diagnostics);
    Result := True;
  finally
    Diagnostics.Free;
  end;
end;

function SupportsVirtualTreeAccessPath(const TreeComponent: TObject): Boolean;
var
  Context: TRttiContext;
  RttiType: TRttiType;
begin
  Result := False;
  if TreeComponent = nil then
    Exit;

  Context := TRttiContext.Create;
  try
    RttiType := Context.GetType(TreeComponent.ClassType);
    if RttiType = nil then
      Exit;

    Result :=
      (RttiType.GetMethod('GetFirst') <> nil) and
      (RttiType.GetMethod('GetNext') <> nil) and
      (RttiType.GetIndexedProperty('Text') <> nil) and
      (RttiType.GetIndexedProperty('CheckState') <> nil);
  finally
    Context.Free;
  end;
end;

function TryFindModuleTreeAccess(const WindowHandle: HWND; out Access: TModuleTreeAccess; out Detail: string): Boolean;
var
  ModuleForm: TCustomForm;
  TreeComponent: TComponent;
  TreeControl: TWinControl;
  VirtualTreeHandle: HWND;
begin
  Result := False;
  Detail := '';
  FillChar(Access, SizeOf(Access), 0);

  VirtualTreeHandle := FindChildWindowByClass(WindowHandle, 'TVirtualStringTree');
  if VirtualTreeHandle <> 0 then
  begin
    AppendModuleSelectionDiagnosticLine('virtual_tree_handle=' + FormatDiagnosticHandle(VirtualTreeHandle));
    AppendVirtualTreeHwndProbeDiagnostics(VirtualTreeHandle, MaxVirtualTreeTopLevelSampleNodes);
    TreeControl := FindControl(VirtualTreeHandle);
    if TreeControl <> nil then
    begin
      AppendModuleSelectionDiagnosticLine('virtual_tree_child_find_control_success=true');
      AppendModuleSelectionDiagnosticLine('virtual_tree_control=' + TreeControl.ClassName + '.' + TreeControl.Name);
      if SupportsVirtualTreeAccessPath(TreeControl) then
      begin
        AppendModuleSelectionDiagnosticLine('virtual_tree_access_supported=true');
        AppendVirtualTreeTopLevelSampleDiagnostics(TreeControl, MaxVirtualTreeTopLevelSampleNodes);
        Access.Kind := mtkVclVirtualTree;
        Access.TreeComponent := TreeControl;
        Access.TreeHandle := VirtualTreeHandle;
        Result := True;
        Exit;
      end
      else
        AppendModuleSelectionDiagnosticLine('virtual_tree_access_supported=false');
    end
    else
    begin
      AppendModuleSelectionDiagnosticLine('virtual_tree_child_find_control_success=false');
      AppendModuleSelectionDiagnosticLine('virtual_tree_control=nil');
    end;
  end
  else
    AppendModuleSelectionDiagnosticLine('virtual_tree_handle=0x00000000');

  if TryResolveModuleSelectionForm(WindowHandle, ModuleForm, Detail) then
  begin
    AppendModuleSelectionDiagnosticLine('module_form=' + ModuleForm.ClassName + '.' + ModuleForm.Name);
    TreeComponent := ModuleForm.FindComponent('vstModules');
    if TreeComponent = nil then
    begin
      AppendModuleSelectionDiagnosticLine('vst_modules=nil');
      Detail := 'Detected Module Selection but could not find the visible module tree (vstModules not found).';
      Exit;
    end;

    AppendModuleSelectionDiagnosticLine('vst_modules=' + TreeComponent.ClassName + '.' + TreeComponent.Name);

    if not SupportsVirtualTreeAccessPath(TreeComponent) then
    begin
      AppendModuleSelectionDiagnosticLine('vst_modules_access_supported=false');
      Detail := 'Detected Module Selection and resolved TfrmModuleSelect.vstModules, but the tree uses an unsupported access path.';
      Exit;
    end;

    AppendModuleSelectionDiagnosticLine('vst_modules_access_supported=true');

    if TreeComponent is TWinControl then
    begin
      TWinControl(TreeComponent).HandleNeeded;
      AppendModuleSelectionDiagnosticLine('vst_modules_handle=' + FormatDiagnosticHandle(TWinControl(TreeComponent).Handle));
    end
    else
      AppendModuleSelectionDiagnosticLine('vst_modules_handle=0x00000000');

    Access.Kind := mtkVclVirtualTree;
    Access.TreeComponent := TreeComponent;
    if TreeComponent is TWinControl then
      Access.TreeHandle := TWinControl(TreeComponent).Handle;
    Result := True;
    Exit;
  end;

  Access.TreeHandle := FindChildWindowByClass(WindowHandle, 'SysTreeView32');
  if Access.TreeHandle <> 0 then
  begin
    AppendModuleSelectionDiagnosticLine('native_tree_handle=' + FormatDiagnosticHandle(Access.TreeHandle));
    Access.Kind := mtkNativeTreeView;
    Result := True;
    Exit;
  end;

  AppendModuleSelectionDiagnosticLine('native_tree_handle=0x00000000');

  if Detail = '' then
    Detail := 'Detected Module Selection but could not find the visible module tree (form not found).';
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

function MakePointerTValue(const Value: Pointer): TValue;
var
  RawValue: Pointer;
begin
  RawValue := Value;
  TValue.Make(@RawValue, TypeInfo(Pointer), Result);
end;

function MakeIntegerTValue(const Value: Integer): TValue;
var
  RawValue: Integer;
begin
  RawValue := Value;
  TValue.Make(@RawValue, TypeInfo(Integer), Result);
end;

function GetPointerFromTValue(const Value: TValue): Pointer;
begin
  Result := nil;
  if Value.IsEmpty then
    Exit;

  Value.ExtractRawData(@Result);
end;

function GetVirtualTreeNodeText(const TreeComponent: TObject; const NodeHandle: HTREEITEM): string;
var
  Value: TValue;
begin
  if TryGetIndexedPropertyValue(TreeComponent, 'Text', [MakePointerTValue(Pointer(NodeHandle)), MakeIntegerTValue(0)], Value) then
    Result := Trim(Value.ToString)
  else
    Result := '';
end;

function GetVirtualTreeNodeChecked(const TreeComponent: TObject; const NodeHandle: HTREEITEM): Boolean;
var
  Value: TValue;
begin
  if not TryGetIndexedPropertyValue(TreeComponent, 'CheckState', [MakePointerTValue(Pointer(NodeHandle))], Value) then
  begin
    Result := False;
    Exit;
  end;

  Result := Value.AsOrdinal >= 2;
end;

function SetVirtualTreeNodeChecked(const TreeComponent: TObject; const NodeHandle: HTREEITEM; const Checked: Boolean): Boolean;
var
  StateOrdinal: Integer;
begin
  if Checked then
    StateOrdinal := 2
  else
    StateOrdinal := 0;

  Result := TrySetIndexedEnumPropertyOrdinal(TreeComponent, 'CheckState', [MakePointerTValue(Pointer(NodeHandle))], StateOrdinal);
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

function ReadNativeTreeVisibleModuleNodes(const TreeHandle: HWND): TModuleNodeArray;
var
  RootHandle: HTREEITEM;
begin
  SetLength(Result, 0);
  RootHandle := HTREEITEM(SendMessage(TreeHandle, TVM_GETNEXTITEM, TVGN_ROOT, 0));
  if RootHandle <> nil then
    CollectTreeNodes(TreeHandle, RootHandle, Result);
end;

function GetVirtualTreeFirstNode(const TreeComponent: TObject): HTREEITEM;
var
  Value: TValue;
begin
  Result := nil;
  if TryInvokeObjectMethod(TreeComponent, 'GetFirst', [], Value) and not Value.IsEmpty then
    Result := HTREEITEM(GetPointerFromTValue(Value));
end;

function GetVirtualTreeNextNode(const TreeComponent: TObject; const NodeHandle: HTREEITEM): HTREEITEM;
var
  Value: TValue;
begin
  Result := nil;
  if TryInvokeObjectMethod(TreeComponent, 'GetNext', [MakePointerTValue(Pointer(NodeHandle))], Value) and not Value.IsEmpty then
    Result := HTREEITEM(GetPointerFromTValue(Value));
end;

function GetAccessibleStateDiagnosticValue(const StateValue: OleVariant): string;
var
  StateBits: Integer;
begin
  Result := 'unknown';
  if VarIsEmpty(StateValue) or VarIsNull(StateValue) then
    Exit;

  try
    StateBits := VarAsType(StateValue, varInteger);
  except
    Exit;
  end;

  if (StateBits and STATE_SYSTEM_MIXED) <> 0 then
    Result := 'mixed'
  else if (StateBits and STATE_SYSTEM_CHECKED) <> 0 then
    Result := 'true'
  else
    Result := 'false';
end;

function TryGetAccessibleChildText(const Accessible: IAccessible; const ChildIndex: Integer; out Text: string): Boolean;
var
  ChildVariant: OleVariant;
  NameValue: WideString;
  Hr: HRESULT;
begin
  Result := False;
  Text := '';
  if Accessible = nil then
    Exit;

  ChildVariant := ChildIndex;
  NameValue := '';
  Hr := Accessible.get_accName(ChildVariant, NameValue);
  if Succeeded(Hr) then
  begin
    Text := Trim(NameValue);
    Result := Text <> '';
    if Result then
      Exit;
  end;

  NameValue := '';
  Hr := Accessible.get_accValue(ChildVariant, NameValue);
  if Succeeded(Hr) then
  begin
    Text := Trim(NameValue);
    Result := Text <> '';
  end;
end;

function GetAccessibleChildCheckedState(const Accessible: IAccessible; const ChildIndex: Integer): string;
var
  ChildVariant: OleVariant;
  StateValue: OleVariant;
begin
  Result := 'unknown';
  if Accessible = nil then
    Exit;

  ChildVariant := ChildIndex;
  StateValue := Unassigned;
  if Succeeded(Accessible.get_accState(ChildVariant, StateValue)) then
    Result := GetAccessibleStateDiagnosticValue(StateValue);
end;

procedure AppendVirtualTreeHwndProbeDiagnostics(const VirtualTreeHandle: HWND; const MaxNodes: Integer);
var
  Accessible: IAccessible;
  ChildCount: Integer;
  ChildIndex: Integer;
  SampleCount: Integer;
  ProbeText: string;
  ProbeChecked: string;
  Hr: HRESULT;
  ComInitHResult: HRESULT;
  ShouldUninitializeCom: Boolean;
begin
  AppendModuleSelectionDiagnosticLine('virtual_tree_hwnd_probe_attempted=' + BoolToDiagnosticValue(VirtualTreeHandle <> 0));
  if VirtualTreeHandle = 0 then
    Exit;

  Accessible := nil;
  ChildCount := 0;
  SampleCount := 0;
  ShouldUninitializeCom := False;

  ComInitHResult := CoInitialize(nil);
  if Succeeded(ComInitHResult) or (ComInitHResult = S_FALSE) then
    ShouldUninitializeCom := True;
  AppendModuleSelectionDiagnosticLine('virtual_tree_hwnd_probe_com_init=' + FormatDiagnosticHResult(ComInitHResult));

  try
    try
      Hr := AccessibleObjectFromWindow(VirtualTreeHandle, OBJID_CLIENT, IID_IAccessible, Accessible);
      AppendModuleSelectionDiagnosticLine('virtual_tree_hwnd_probe_accessible=' + BoolToDiagnosticValue(Succeeded(Hr)));
      AppendModuleSelectionDiagnosticLine('virtual_tree_hwnd_probe_accessible_hresult=' + FormatDiagnosticHResult(Hr));
      if not Succeeded(Hr) then
        Exit;

      Hr := Accessible.get_accChildCount(ChildCount);
      AppendModuleSelectionDiagnosticLine('virtual_tree_hwnd_probe_child_count_readable=' + BoolToDiagnosticValue(Succeeded(Hr)));
      AppendModuleSelectionDiagnosticLine('virtual_tree_hwnd_probe_child_count_hresult=' + FormatDiagnosticHResult(Hr));
      if not Succeeded(Hr) then
        Exit;

      AppendModuleSelectionDiagnosticLine('virtual_tree_hwnd_probe_child_count=' + IntToStr(ChildCount));

      for ChildIndex := 1 to ChildCount do
      begin
        ProbeText := '';
        ProbeChecked := GetAccessibleChildCheckedState(Accessible, ChildIndex);
        TryGetAccessibleChildText(Accessible, ChildIndex, ProbeText);
        if (ProbeText = '') and (ProbeChecked = 'unknown') then
          Continue;

        AppendModuleSelectionDiagnosticLine(
          'virtual_tree_hwnd_probe_top_level_sample[' + IntToStr(SampleCount) + ']=' +
          'name=' + FormatDiagnosticText(ProbeText) +
          ',checked=' + ProbeChecked
        );
        Inc(SampleCount);
        if SampleCount >= MaxNodes then
          Break;
      end;

      AppendModuleSelectionDiagnosticLine('virtual_tree_hwnd_probe_top_level_sample_count=' + IntToStr(SampleCount));
    except
      on E: Exception do
        AppendModuleSelectionDiagnosticLine('virtual_tree_hwnd_probe_error=' + FormatDiagnosticText(E.Message));
    end;
  finally
    if ShouldUninitializeCom then
      CoUninitialize;
  end;
end;

procedure AppendVirtualTreeTopLevelSampleDiagnostics(const TreeComponent: TObject; const MaxNodes: Integer);
var
  CurrentHandle: HTREEITEM;
  SampleIndex: Integer;
begin
  try
    SampleIndex := 0;
    CurrentHandle := GetVirtualTreeFirstNode(TreeComponent);
    while (CurrentHandle <> nil) and (SampleIndex < MaxNodes) do
    begin
      AppendModuleSelectionDiagnosticLine(
        'virtual_tree_top_level_sample[' + IntToStr(SampleIndex) + ']=' +
        'name=' + FormatDiagnosticText(GetVirtualTreeNodeText(TreeComponent, CurrentHandle)) +
        ',checked=' + BoolToDiagnosticValue(GetVirtualTreeNodeChecked(TreeComponent, CurrentHandle))
      );
      Inc(SampleIndex);
      CurrentHandle := GetVirtualTreeNextNode(TreeComponent, CurrentHandle);
    end;

    AppendModuleSelectionDiagnosticLine('virtual_tree_top_level_sample_count=' + IntToStr(SampleIndex));
  except
    on E: Exception do
      AppendModuleSelectionDiagnosticLine('virtual_tree_top_level_sample_error=' + FormatDiagnosticText(E.Message));
  end;
end;

function ReadVirtualTreeVisibleModuleNodes(const TreeComponent: TObject): TModuleNodeArray;
var
  CurrentHandle: HTREEITEM;
begin
  SetLength(Result, 0);
  CurrentHandle := GetVirtualTreeFirstNode(TreeComponent);
  while CurrentHandle <> nil do
  begin
    AppendModuleNode(Result, CurrentHandle, GetVirtualTreeNodeText(TreeComponent, CurrentHandle), GetVirtualTreeNodeChecked(TreeComponent, CurrentHandle));
    CurrentHandle := GetVirtualTreeNextNode(TreeComponent, CurrentHandle);
  end;
end;

function ReadVisibleModuleNodes(const TreeAccess: TModuleTreeAccess): TModuleNodeArray;
begin
  case TreeAccess.Kind of
    mtkVclVirtualTree:
      Result := ReadVirtualTreeVisibleModuleNodes(TreeAccess.TreeComponent);
  else
    Result := ReadNativeTreeVisibleModuleNodes(TreeAccess.TreeHandle);
  end;
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

function ReadStableVisibleModuleNodes(const TreeAccess: TModuleTreeAccess): TModuleNodeArray;
var
  Attempt: Integer;
begin
  for Attempt := 1 to 5 do
  begin
    Result := ReadVisibleModuleNodes(TreeAccess);
    if (Length(Result) = 0) or (BuildSelectedModules(Result) <> '') or (Attempt = 5) then
      Exit;

    Sleep(200);
  end;
end;

procedure SetModuleNodeChecked(const TreeAccess: TModuleTreeAccess; const NodeHandle: HTREEITEM; const Checked: Boolean);
begin
  case TreeAccess.Kind of
    mtkVclVirtualTree:
      SetVirtualTreeNodeChecked(TreeAccess.TreeComponent, NodeHandle, Checked);
  else
    SetTreeItemChecked(TreeAccess.TreeHandle, NodeHandle, Checked);
  end;
end;

function TryCaptureSelectedModules(const WindowHandle: HWND; out SelectedModules: string; out Detail: string): Boolean;
var
  TreeAccess: TModuleTreeAccess;
  VisibleNodes: TModuleNodeArray;
begin
  Result := False;
  SelectedModules := '';
  Detail := '';

  if not TryFindModuleTreeAccess(WindowHandle, TreeAccess, Detail) then
    Exit;

  VisibleNodes := ReadStableVisibleModuleNodes(TreeAccess);
  if Length(VisibleNodes) = 0 then
  begin
    Detail := 'Detected Module Selection but could not read any visible module nodes.';
    Exit;
  end;

  SelectedModules := BuildSelectedModules(VisibleNodes);
  Detail := 'Captured the current Module Selection state from the visible module tree.';
  Result := SelectedModules <> '';
end;

function TryReadSessionSelectedModules(out SelectedModules: string; out Detail: string): Boolean;
var
  SessionPluginsPath: string;
  PluginLines: TStringList;
  SelectedNames: TStringList;
  LineIndex: Integer;
  PluginLine: string;
  PluginName: string;
  HasExplicitActiveMarkers: Boolean;
begin
  Result := False;
  SelectedModules := '';
  Detail := '';

  if Trim(GSession.SessionPath) = '' then
  begin
    Detail := 'Module Selection evidence fallback could not read session plugins.txt because the hook session path was missing.';
    Exit;
  end;

  SessionPluginsPath := IncludeTrailingPathDelimiter(GSession.SessionPath) + 'plugins.txt';
  AppendModuleSelectionDiagnosticLine('session_plugins_fallback_path=' + SessionPluginsPath);
  if not FileExists(SessionPluginsPath) then
  begin
    Detail := 'Module Selection evidence fallback could not find the session plugins.txt file.';
    AppendModuleSelectionDiagnosticLine('session_plugins_fallback_exists=false');
    Exit;
  end;

  AppendModuleSelectionDiagnosticLine('session_plugins_fallback_exists=true');
  PluginLines := TStringList.Create;
  SelectedNames := NewModuleNameList;
  try
    PluginLines.LoadFromFile(SessionPluginsPath);
    HasExplicitActiveMarkers := False;
    for LineIndex := 0 to PluginLines.Count - 1 do
    begin
      PluginLine := Trim(PluginLines[LineIndex]);
      if (PluginLine <> '') and (PluginLine[1] <> '#') and PluginLine.StartsWith('*') then
      begin
        HasExplicitActiveMarkers := True;
        Break;
      end;
    end;

    for LineIndex := 0 to PluginLines.Count - 1 do
    begin
      PluginLine := Trim(PluginLines[LineIndex]);
      if PluginLine = '' then
        Continue;
      if PluginLine[1] = '#' then
        Continue;

      if HasExplicitActiveMarkers and (not PluginLine.StartsWith('*')) then
        Continue;

      PluginName := TrimLeft(PluginLine);
      if (PluginName <> '') and (PluginName[1] = '*') then
        Delete(PluginName, 1, 1);
      PluginName := Trim(PluginName);
      if PluginName <> '' then
        SelectedNames.Add(PluginName);
    end;

    SelectedModules := JoinModuleNames(SelectedNames);
    AppendModuleSelectionDiagnosticLine('session_plugins_fallback_selected_count=' + IntToStr(SelectedNames.Count));
    Result := SelectedModules <> '';
    if Result then
      Detail := 'Could not capture the visible module tree; using the session plugins.txt file as selected_modules evidence.'
    else
      Detail := 'Module Selection evidence fallback found the session plugins.txt file, but it did not contain any usable plugin entries.';
  finally
    SelectedNames.Free;
    PluginLines.Free;
  end;
end;

function TryCaptureSelectedModulesOrFallback(const WindowHandle: HWND; out SelectedModules: string; out Detail: string): Boolean;
var
  CaptureDetail: string;
  FallbackDetail: string;
begin
  Result := False;
  SelectedModules := '';
  Detail := '';

  if TryCaptureSelectedModules(WindowHandle, SelectedModules, CaptureDetail) then
  begin
    Detail := CaptureDetail;
    Result := True;
    Exit;
  end;

  if Trim(CaptureDetail) <> '' then
    AppendModuleSelectionDiagnosticLine('tree_capture_detail=' + CaptureDetail);

  if TryReadSessionSelectedModules(SelectedModules, FallbackDetail) then
  begin
    Detail := FallbackDetail;
    Result := True;
    Exit;
  end;

  if (Trim(CaptureDetail) <> '') and (Trim(FallbackDetail) <> '') then
    Detail := CaptureDetail + ' Fallback detail: ' + FallbackDetail
  else if Trim(CaptureDetail) <> '' then
    Detail := CaptureDetail
  else
    Detail := FallbackDetail;
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

function EnumStartupInterstitialWindowProc(WindowHandle: HWND; Parameter: LPARAM): BOOL; stdcall;
var
  Caption: string;
  ClassName: string;
begin
  Caption := Trim(GetWindowTextValue(WindowHandle));
  ClassName := Trim(GetWindowClassNameValue(WindowHandle));
  if SameText(ClassName, StartupWhatsNewClassName)
     or Caption.StartsWith(StartupWhatsNewCaptionPrefix, True)
     or SameText(ClassName, StartupDeveloperMessageClassName)
     or Caption.StartsWith(StartupDeveloperMessageCaptionPrefix, True)
  then
  begin
    PWindowHandle(Parameter)^ := WindowHandle;
    Result := False;
    Exit;
  end;

  Result := True;
end;

procedure EnumCurrentProcessWindows(ResultHandle: PWindowHandle; const Callback: TFNWndEnumProc);
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
        if not EnumThreadWindows(ThreadEntry.th32ThreadID, Callback, LPARAM(ResultHandle)) then
          Exit;
      end;
      ThreadEntry.dwSize := SizeOf(ThreadEntry);
    until not Thread32Next(Snapshot, ThreadEntry);
  finally
    CloseHandle(Snapshot);
  end;
end;

function EnumProcessWindowSnapshotProc(WindowHandle: HWND; Parameter: LPARAM): BOOL; stdcall;
var
  Context: PWindowSnapshotContext;
begin
  Context := PWindowSnapshotContext(Parameter);
  Inc(Context.ChildCount);
  if Context.ChildLogged < MaxDiagnosticChildWindows then
  begin
    Context.Lines.Add(FormatWindowSnapshotLine('process_window[' + IntToStr(Context.ChildLogged) + ']=', WindowHandle, GetParent(WindowHandle)));
    Inc(Context.ChildLogged);
  end;
  Result := True;
end;

procedure CaptureCurrentProcessWindowDiagnostics;
var
  Snapshot: THandle;
  ThreadEntry: TThreadEntry32;
  Lines: TStringList;
  SnapshotContext: TWindowSnapshotContext;
begin
  Snapshot := CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
  if Snapshot = INVALID_HANDLE_VALUE then
    Exit;

  Lines := TStringList.Create;
  try
    SnapshotContext.Lines := Lines;
    SnapshotContext.ChildCount := 0;
    SnapshotContext.ChildLogged := 0;

    ThreadEntry.dwSize := SizeOf(ThreadEntry);
    if Thread32First(Snapshot, ThreadEntry) then
      repeat
        if ThreadEntry.th32OwnerProcessID = GetCurrentProcessId then
          EnumThreadWindows(ThreadEntry.th32ThreadID, @EnumProcessWindowSnapshotProc, LPARAM(@SnapshotContext));
        ThreadEntry.dwSize := SizeOf(ThreadEntry);
      until not Thread32Next(Snapshot, ThreadEntry);

    AppendModuleSelectionDiagnosticLine('process_window_count=' + IntToStr(SnapshotContext.ChildCount));
    AppendModuleSelectionDiagnosticLine('process_window_logged=' + IntToStr(SnapshotContext.ChildLogged));
    if Lines.Count > 0 then
      AppendModuleSelectionDiagnosticLine(Lines.Text.Trim);
  finally
    Lines.Free;
    CloseHandle(Snapshot);
  end;
end;

function FindModuleSelectionWindow: HWND;
begin
  Result := 0;
  EnumCurrentProcessWindows(@Result, @EnumModuleSelectionWindowProc);
end;

function FindStartupInterstitialWindow: HWND;
begin
  Result := 0;
  EnumCurrentProcessWindows(@Result, @EnumStartupInterstitialWindowProc);
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

function TryDismissStartupInterstitial(const WindowHandle: HWND; out Method: string): Boolean;
var
  OkButton: HWND;
begin
  Method := '';
  if WindowHandle = 0 then
  begin
    Result := False;
    Exit;
  end;

  OkButton := FindOkButton(WindowHandle);
  if OkButton <> 0 then
  begin
    PostMessage(OkButton, BM_CLICK, 0, 0);
    Method := 'button-click';
    Result := True;
    Exit;
  end;

  PostMessage(WindowHandle, WM_CLOSE, 0, 0);
  Method := 'wm-close';
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
  WriteModuleSelectionStatus(GSession, Status, Detail, SelectionDetected, SelectionConfirmed, GSelectedModules, GSelectionDiagnostics);
end;

function ModuleSelectionWorkerProc(Parameter: Pointer): Integer;
var
  ModuleSelectionWindow: HWND;
  StartupInterstitialWindow: HWND;
  CaptureDetail: string;
  FailureDetail: string;
begin
  Result := 0;
  try
    WriteModuleSelectionStatus(GSession, 'loaded', 'Module Selection worker thread started.', False, False, '', GSelectionDiagnostics);
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
        StartupInterstitialWindow := FindStartupInterstitialWindow;
        if StartupInterstitialWindow <> 0 then
        begin
          if TryDismissStartupInterstitial(StartupInterstitialWindow, CaptureDetail) then
            WriteWorkerCheckpoint('Dismissed startup interstitial before Module Selection using ' + CaptureDetail + '.')
          else
            WriteWorkerCheckpoint('Detected startup interstitial before Module Selection but could not dismiss it.');
          Sleep(ModuleSelectionPollIntervalMs);
          Continue;
        end;

        if GSelectionDetected and GSelectionAttempted then
        begin
          CompleteModuleSelection('module-selection-confirmed', 'Detected Module Selection and confirmed the current selection.', True, True);
          Exit;
        end;

        Sleep(ModuleSelectionPollIntervalMs);
        Continue;
      end;

      GSelectionDetected := True;
      if GSelectionDiagnostics = '' then
        CaptureModuleSelectionDiagnostics(ModuleSelectionWindow, nil);

      if not GSelectionAttempted then
      begin
        if (GSelectedModules = '') and TryCaptureSelectedModulesOrFallback(ModuleSelectionWindow, GSelectedModules, CaptureDetail) then
          WriteWorkerCheckpoint(CaptureDetail)
        else if GSelectedModules = '' then
        begin
          if Trim(CaptureDetail) = '' then
            CaptureDetail := 'Detected Module Selection but could not determine selected_modules evidence.';
          WriteWorkerCheckpoint(CaptureDetail);
          FailureDetail := CaptureDetail;
          CompleteModuleSelection('failed', FailureDetail, True, False);
          Exit;
        end;

        if not TryConfirmModuleSelection(ModuleSelectionWindow, CaptureDetail) then
        begin
          CompleteModuleSelection('failed', 'Detected Module Selection but could not trigger confirmation for the current selection.', True, False);
          Exit;
        end;

        GSelectionAttempted := True;
        if WaitForModuleSelectionClose(ModuleSelectionWindow, ModuleSelectionCloseWaitMs) then
        begin
          CompleteModuleSelection('module-selection-confirmed', 'Detected Module Selection and confirmed the current selection.', True, True);
          Exit;
        end;

        WriteModuleSelectionStatus(GSession, 'loaded', 'Detected Module Selection and triggered confirmation for the current selection.', True, False, GSelectedModules, GSelectionDiagnostics);
      end;

      Sleep(ModuleSelectionPollIntervalMs);
    end;

    if GSelectionDetected and GSelectionAttempted then
    begin
      CompleteModuleSelection('failed', 'Detected Module Selection but it did not close after confirmation was attempted for the current selection.', True, False);
    end
    else
    begin
      CaptureCurrentProcessWindowDiagnostics;
      CompleteModuleSelection('failed', 'Timed out waiting for Module Selection while the current selection was active.', False, False);
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
  if Trim(Session.SessionId) = '' then
    ValidationMessage := 'Missing XEDIT_CLI_HOOK_SESSION_ID.'
  else if Trim(Session.SessionPath) = '' then
    ValidationMessage := 'Missing XEDIT_CLI_HOOK_SESSION_PATH.'
  else
    ValidationMessage := '';

  if ValidationMessage <> '' then
  begin
    WriteLoadStatus(Session, 'failed', ValidationMessage);
    Result := False;
    Exit;
  end;

  try
    GSession := Session;
    GModuleSelectionStartedTick := GetTickCount;
    GSelectionDetected := False;
    GSelectionAttempted := False;
    GSelectionCompleted := False;
    GWorkerLoopCount := 0;
    GSelectedModules := '';
    GSelectionDiagnostics := '';
    WorkerThreadId := 0;
    WorkerThreadHandle := BeginThread(nil, 0, ModuleSelectionWorkerProc, nil, 0, WorkerThreadId);
    if WorkerThreadHandle = 0 then
      raise Exception.Create('Failed to start Module Selection worker thread.');
    CloseHandle(WorkerThreadHandle);

    WriteModuleSelectionStatus(Session, 'loaded', 'Init completed. Waiting to confirm the current Module Selection.', False, False, '', GSelectionDiagnostics);

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
