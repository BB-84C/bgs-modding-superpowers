unit HookSession;

interface

type
  THookSession = record
    SessionId: string;
    SessionPath: string;
  end;

function ReadHookSession: THookSession;
function DescribeHookSessionValidation(const Session: THookSession): string;

implementation

uses
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
end;

function DescribeHookSessionValidation(const Session: THookSession): string;
begin
  if Session.SessionId = '' then
    Result := 'Missing XEDIT_CLI_HOOK_SESSION_ID.'
  else if Session.SessionPath = '' then
    Result := 'Missing XEDIT_CLI_HOOK_SESSION_PATH.'
  else
    Result := '';
end;

end.
