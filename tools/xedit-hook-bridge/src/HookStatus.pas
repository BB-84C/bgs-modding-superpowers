unit HookStatus;

interface

uses
  HookSession;

procedure WriteLoadStatus(const Session: THookSession; const Status: string; const Detail: string);
procedure WriteModuleSelectionStatus(const Session: THookSession; const Status: string; const Detail: string; const SelectionDetected: LongBool; const SelectionConfirmed: LongBool; const SelectedModules: string; const Diagnostics: string = '');

implementation

uses
  Classes,
  SysUtils,
  Windows;

function GetSystemTempPath: string;
var
  Buffer: array[0..MAX_PATH] of Char;
  LengthWritten: DWORD;
begin
  LengthWritten := Windows.GetTempPath(MAX_PATH, Buffer);
  if LengthWritten > 0 then
    Result := IncludeTrailingPathDelimiter(string(Buffer))
  else
    Result := IncludeTrailingPathDelimiter(ExtractFilePath(ParamStr(0)));
end;

function GetSafeStatusFileToken(const Value: string): string;
var
  InvalidChar: Char;
  ReservedName: string;
  BaseName: string;
  ExtensionPart: string;
  DotIndex: Integer;
  Index: Integer;
begin
  Result := Value;
  if Result = '' then
    Exit;

  for Index := 1 to Length(Result) do
    if Ord(Result[Index]) <= 31 then
      Result[Index] := '_';

  for InvalidChar in ['\', '/', ':', '*', '?', '"', '<', '>', '|'] do
    Result := Result.Replace(InvalidChar, '_');

  while (Length(Result) > 0) and ((Result[Length(Result)] = '.') or (Result[Length(Result)] = ' ') or (Ord(Result[Length(Result)]) <= 31)) do
    SetLength(Result, Length(Result) - 1);

  if Result = '' then
  begin
    Result := 'missing-session';
    Exit;
  end;

  BaseName := Result;
  ExtensionPart := '';
  DotIndex := Pos('.', BaseName);
  if DotIndex > 0 then
  begin
    ExtensionPart := Copy(BaseName, DotIndex, MaxInt);
    BaseName := Copy(BaseName, 1, DotIndex - 1);
  end;

  for ReservedName in ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'] do
    if SameText(BaseName, ReservedName) then
    begin
      BaseName := '_' + BaseName + '_session';
      Break;
    end;

  Result := BaseName + ExtensionPart;
end;

function GetHookStatusPath(const Session: THookSession): string;
var
  SessionRoot: string;
  SafeSessionId: string;
begin
  SessionRoot := Session.SessionPath;
  if SessionRoot <> '' then
  begin
    ForceDirectories(SessionRoot);
    Result := IncludeTrailingPathDelimiter(SessionRoot) + 'hook-status.txt';
    Exit;
  end;

  SessionRoot := IncludeTrailingPathDelimiter(GetSystemTempPath) + 'xedit-hook-bridge-blockers';
  ForceDirectories(SessionRoot);

  SafeSessionId := GetSafeStatusFileToken(Session.SessionId);
  if SafeSessionId <> '' then
    Result := IncludeTrailingPathDelimiter(SessionRoot) + SafeSessionId + '-hook-status.txt'
  else
    Result := IncludeTrailingPathDelimiter(SessionRoot) + 'missing-session-hook-status.txt';
end;

function GetFallbackStatusPath(const Session: THookSession): string;
var
  FallbackSession: THookSession;
begin
  FallbackSession := Session;
  FallbackSession.SessionPath := '';
  Result := GetHookStatusPath(FallbackSession);
end;

function BoolToStatusValue(const Value: LongBool): string;
begin
  if Value then
    Result := 'true'
  else
    Result := 'false';
end;

procedure WriteStatusLines(const Session: THookSession; const StatusPath: string; const Status: string; const Detail: string; const SelectionDetected: LongBool; const SelectionConfirmed: LongBool; const SelectedModules: string; const Diagnostics: string; const IncludeSelectionState: Boolean);
var
  Lines: TStringList;
  DiagnosticLines: TStringList;
  DiagnosticIndex: Integer;
begin
  Lines := TStringList.Create;
  try
    Lines.Add('status=' + Status);
    Lines.Add('session_id=' + Session.SessionId);
    if IncludeSelectionState then
    begin
      Lines.Add('selection_detected=' + BoolToStatusValue(SelectionDetected));
      Lines.Add('selection_confirmed=' + BoolToStatusValue(SelectionConfirmed));
      if SelectedModules <> '' then
        Lines.Add('selected_modules=' + SelectedModules);
    end;
    if Detail <> '' then
      Lines.Add('detail=' + Detail);
    if Diagnostics <> '' then
    begin
      DiagnosticLines := TStringList.Create;
      try
        DiagnosticLines.Text := Diagnostics;
        for DiagnosticIndex := 0 to DiagnosticLines.Count - 1 do
          if Trim(DiagnosticLines[DiagnosticIndex]) <> '' then
            Lines.Add(DiagnosticLines[DiagnosticIndex]);
      finally
        DiagnosticLines.Free;
      end;
    end;
    Lines.SaveToFile(StatusPath);
  finally
    Lines.Free;
  end;
end;

procedure WriteStatusFile(const Session: THookSession; const Status: string; const Detail: string; const SelectionDetected: LongBool; const SelectionConfirmed: LongBool; const SelectedModules: string; const Diagnostics: string; const IncludeSelectionState: Boolean);
var
  StatusPath: string;
  FallbackPath: string;
begin
  StatusPath := GetHookStatusPath(Session);
  try
    WriteStatusLines(Session, StatusPath, Status, Detail, SelectionDetected, SelectionConfirmed, SelectedModules, Diagnostics, IncludeSelectionState);
  except
    FallbackPath := GetFallbackStatusPath(Session);
    if not SameText(FallbackPath, StatusPath) then
      WriteStatusLines(Session, FallbackPath, Status, Detail, SelectionDetected, SelectionConfirmed, SelectedModules, Diagnostics, IncludeSelectionState)
    else
      raise;
  end;
end;

procedure WriteLoadStatus(const Session: THookSession; const Status: string; const Detail: string);
begin
  WriteStatusFile(Session, Status, Detail, False, False, '', '', False);
end;

procedure WriteModuleSelectionStatus(const Session: THookSession; const Status: string; const Detail: string; const SelectionDetected: LongBool; const SelectionConfirmed: LongBool; const SelectedModules: string; const Diagnostics: string = '');
begin
  WriteStatusFile(Session, Status, Detail, SelectionDetected, SelectionConfirmed, SelectedModules, Diagnostics, True);
end;

end.
