#define MyAppName "JobDocs"
#define MyAppVersion GetEnv("RELEASE_VERSION")
#define MyAppPublisher "i-machine-things"
#define MyAppURL "https://github.com/i-machine-things/JobDocs"
#define MyAppExeName "JobDocs.exe"
#define MyAppId "{{B7C4D2A1-5E8F-4A9B-8C2D-3E4F5A6B7C8D}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\installer_out
OutputBaseFilename=JobDocs-{#MyAppVersion}-windows-setup
SetupIconFile=..\windows\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ChangesEnvironment=yes


[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "readonly";    Description: "Read-Only (Search Only) — only install the Search tab"; GroupDescription: "Installation Type:"

[Dirs]
Name: "{app}\plugins"

[Files]
; Launcher executable
Source: "..\JobDocs.exe";          DestDir: "{app}"; Flags: ignoreversion

; Application icon (used directly by shortcuts to bypass EXE icon extraction)
Source: "..\windows\icon.ico";     DestDir: "{app}"; Flags: ignoreversion

; Python source tree (runs via runtime\pythonw.exe)
Source: "..\app\*";                DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs

; Embedded Python 3.12 runtime with pre-installed dependencies
Source: "..\runtime\*";            DestDir: "{app}\runtime"; Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallDelete]
; Force-remove everything including runtime-created files (e.g. __pycache__,
; pip-installed plugin deps) and user-installed plugins.
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\runtime"
Type: filesandordirs; Name: "{app}\plugins"
Type: filesandordirs; Name: "{app}"

[Icons]
Name: "{group}\{#MyAppName}";                          Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}";    Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";                    Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  KeepSettings: Boolean;

const
  SysEnvKey  = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';
  UserEnvKey = 'Environment';

procedure AddToPath(AppDir: string);
{ Append AppDir to the correct PATH hive (HKCU for per-user, HKLM for all-users).
  Safe to call on upgrade — skipped when AppDir is already present. }
var
  RootKey: Integer;
  SubKey: string;
  EnvPath: string;
begin
  if IsAdminInstallMode then
  begin
    RootKey := HKEY_LOCAL_MACHINE;
    SubKey  := SysEnvKey;
  end else
  begin
    RootKey := HKEY_CURRENT_USER;
    SubKey  := UserEnvKey;
  end;

  if not RegQueryStringValue(RootKey, SubKey, 'Path', EnvPath) then
    EnvPath := '';

  if Pos(';' + Uppercase(AppDir) + ';', ';' + Uppercase(EnvPath) + ';') > 0 then
    Exit; { already present }

  if EnvPath = '' then
    EnvPath := AppDir
  else
    EnvPath := EnvPath + ';' + AppDir;

  RegWriteExpandStringValue(RootKey, SubKey, 'Path', EnvPath);
end;

procedure RemoveFromPath(AppDir: string);
{ Remove AppDir from whichever PATH hive was used during install. }
var
  RootKey: Integer;
  SubKey: string;
  EnvPath: string;
  SearchStr: string;
  P: Integer;
begin
  if IsAdminInstallMode then
  begin
    RootKey := HKEY_LOCAL_MACHINE;
    SubKey  := SysEnvKey;
  end else
  begin
    RootKey := HKEY_CURRENT_USER;
    SubKey  := UserEnvKey;
  end;
  if not RegQueryStringValue(RootKey, SubKey, 'Path', EnvPath) then Exit;
  SearchStr := ';' + AppDir;
  P := Pos(LowerCase(SearchStr + ';'), LowerCase(EnvPath + ';'));
  if P > 0 then
  begin
    Delete(EnvPath, P, Length(SearchStr));
    RegWriteExpandStringValue(RootKey, SubKey, 'Path', EnvPath);
  end;
end;

procedure InitializeWizard();
{ Pre-check the Read-Only task if that's what was selected on a previous
  install of this app, so an update installer defaults to the same variant
  instead of silently reverting a read-only (search-only) machine to full.

  Selects by the task's [Tasks] Name ("readonly"), the stable identifier,
  via WizardSelectTasks — not by matching the Description text shown in
  WizardForm.TasksList, which would silently stop matching if that text
  ever changes. }
begin
  if GetPreviousData('InstallType', 'full') = 'readonly' then
    WizardSelectTasks('readonly');
end;

procedure RegisterPreviousData(PreviousDataKey: Integer);
{ Setup calls this automatically to persist "previous data" for this AppId
  (keyed by PreviousDataKey, independent of install path) so the next
  install/update of this app can recall the chosen install type. }
begin
  if WizardIsTaskSelected('readonly') then
    SetPreviousData(PreviousDataKey, 'InstallType', 'readonly')
  else
    SetPreviousData(PreviousDataKey, 'InstallType', 'full');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  MarkerFile: String;
begin
  if CurStep = ssPostInstall then
  begin
    AddToPath(ExpandConstant('{app}'));

    { Drop a marker file the app itself reads at startup to switch into
      read-only (search-only) mode. This is a UI/kiosk convenience, not
      access control -- a per-user install grants the same account write
      access to this file, so it can be deleted to unlock the full app.
      Real enforcement needs a separately managed account with the install
      directory locked down. }
    MarkerFile := ExpandConstant('{app}\readonly.marker');
    if WizardIsTaskSelected('readonly') then
      SaveStringToFile(MarkerFile, 'search-only' + #13#10, False)
    else if FileExists(MarkerFile) then
      DeleteFile(MarkerFile);
  end;
end;

function InitializeUninstall(): Boolean;
begin
  KeepSettings := MsgBox(
    'Do you want to keep your JobDocs settings and history?' + #13#10 + #13#10 +
    'Yes  — keep settings, jobs history, and installed plugins'' data' + #13#10 +
    'No   — remove everything including settings and history',
    mbConfirmation, MB_YESNO) = IDYES;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ConfigDir: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RemoveFromPath(ExpandConstant('{app}'));
    if not KeepSettings then
    begin
      ConfigDir := ExpandConstant('{localappdata}\JobDocs');
      if DirExists(ConfigDir) then
        DelTree(ConfigDir, True, True, True);
    end;
  end;
end;
