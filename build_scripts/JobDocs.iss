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

[Registry]
; Add install directory to PATH so JobDocs.exe is callable from the command line.
; Per-user install writes to HKCU; all-users (admin) install writes to HKLM.
; Each entry is gated by its own check to prevent duplicates and wrong-hive writes.
Root: HKCU; Subkey: "Environment"; \
  ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; \
  Check: NeedsAddPathUser(ExpandConstant('{app}'))
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; \
  ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; \
  Check: NeedsAddPathAdmin(ExpandConstant('{app}'))

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

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

{ True when AppDir is absent from HKCU PATH — used for per-user installs. }
function NeedsAddPathUser(AppDir: string): Boolean;
var
  EnvPath: string;
begin
  Result := False;
  if IsAdminInstallMode then Exit;
  if not RegQueryStringValue(HKEY_CURRENT_USER, UserEnvKey, 'Path', EnvPath) then
  begin
    Result := True; Exit;
  end;
  Result := Pos(';' + Uppercase(AppDir) + ';', ';' + Uppercase(EnvPath) + ';') = 0;
end;

{ True when AppDir is absent from HKLM PATH — used for all-users (admin) installs. }
function NeedsAddPathAdmin(AppDir: string): Boolean;
var
  EnvPath: string;
begin
  Result := False;
  if not IsAdminInstallMode then Exit;
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE, SysEnvKey, 'Path', EnvPath) then
  begin
    Result := True; Exit;
  end;
  Result := Pos(';' + Uppercase(AppDir) + ';', ';' + Uppercase(EnvPath) + ';') = 0;
end;

{ Removes AppDir from whichever PATH hive was used during install. }
procedure RemoveFromPath(AppDir: string);
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
