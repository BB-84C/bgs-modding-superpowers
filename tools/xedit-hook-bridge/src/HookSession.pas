unit HookSession;

interface

type
  THookSession = record
    SessionId: string;
    SessionPath: string;
    LoadMode: string;
    Plugins: string;
  end;

function ReadHookSession: THookSession;
function DescribeHookSessionValidation(const Session: THookSession): string;
function IsAllLoadMode(const Session: THookSession): Boolean;
function IsOnlyLoadMode(const Session: THookSession): Boolean;
function IsExcludeLoadMode(const Session: THookSession): Boolean;
function UsesSubsetLoadMode(const Session: THookSession): Boolean;

implementation

uses
  SysUtils,
  Windows;

function ReadEnvironmentVariableValue(const Name: string): string;
var
  RequiredSize: DWORD;
begin
  Result := '';
  RequiredSize := GetEnvironmentVariable(PChar(Name), nil, 0);
  if RequiredSize = 0 then
    Exit;

  SetLength(Result, RequiredSize - 1);
  if Length(Result) > 0 then
    GetEnvironmentVariable(PChar(Name), PChar(Result), RequiredSize);
end;

function ReadHookSession: THookSession;
begin
  Result.SessionId := ReadEnvironmentVariableValue('XEDIT_CLI_HOOK_SESSION_ID');
  Result.SessionPath := ReadEnvironmentVariableValue('XEDIT_CLI_HOOK_SESSION_PATH');
  Result.LoadMode := ReadEnvironmentVariableValue('XEDIT_CLI_HOOK_LOAD_MODE');
  Result.Plugins := ReadEnvironmentVariableValue('XEDIT_CLI_HOOK_PLUGINS');
end;

function DescribeHookSessionValidation(const Session: THookSession): string;
begin
  if Session.SessionId = '' then
    Result := 'Missing XEDIT_CLI_HOOK_SESSION_ID.'
  else if Session.SessionPath = '' then
    Result := 'Missing XEDIT_CLI_HOOK_SESSION_PATH.'
  else if Session.LoadMode = '' then
    Result := 'Missing XEDIT_CLI_HOOK_LOAD_MODE.'
  else
    Result := '';
end;

function IsAllLoadMode(const Session: THookSession): Boolean;
begin
  Result := SameText(Trim(Session.LoadMode), 'all');
end;

function IsOnlyLoadMode(const Session: THookSession): Boolean;
begin
  Result := SameText(Trim(Session.LoadMode), 'only');
end;

function IsExcludeLoadMode(const Session: THookSession): Boolean;
begin
  Result := SameText(Trim(Session.LoadMode), 'exclude');
end;

function UsesSubsetLoadMode(const Session: THookSession): Boolean;
begin
  Result := IsOnlyLoadMode(Session) or IsExcludeLoadMode(Session);
end;

end.
