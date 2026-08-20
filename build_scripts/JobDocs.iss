; JobDocs Kiosk is a separate installer/product built from this same script
; via `iscc /DKIOSK JobDocs.iss` -- own AppId, own default install dir, own
; release asset (not a Task checkbox on the main installer). It's a
; search-only kiosk build for shared/shop-floor machines; see the [Files]
; section below for what that excludes and main.py's _is_readonly_install().
#define MyAppVersion GetEnv("RELEASE_VERSION")
#define MyAppPublisher "i-machine-things"
#define MyAppURL "https://github.com/i-machine-things/JobDocs"
#define MyAppExeName "JobDocs.exe"

#ifdef KIOSK
#define MyAppName "JobDocs Kiosk"
#define MyAppId "{{A2FC3EFB-053C-4FE6-A2F7-6A56CDE7E4D7}"
#else
#define MyAppName "JobDocs"
#define MyAppId "{{B7C4D2A1-5E8F-4A9B-8C2D-3E4F5A6B7C8D}"
#endif

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
#ifdef KIOSK
OutputBaseFilename=JobDocs-Kiosk-{#MyAppVersion}-windows-setup
#else
OutputBaseFilename=JobDocs-{#MyAppVersion}-windows-setup
#endif
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

[Dirs]
Name: "{app}\plugins"

[Files]
; Launcher executable
Source: "..\JobDocs.exe";          DestDir: "{app}"; Flags: ignoreversion

; Application icon (used directly by shortcuts to bypass EXE icon extraction)
Source: "..\windows\icon.ico";     DestDir: "{app}"; Flags: ignoreversion

#ifdef KIOSK
; JobDocs Kiosk: only the files the Search module and its shared/core
; dependencies need. Bulk, Job, Quote, Settings, etc. are never copied, so
; there is no write-capable module code to unlock even if readonly.marker
; is later deleted -- see main.py's _is_readonly_install().
Source: "..\app\main.py";              DestDir: "{app}\app";                 Flags: ignoreversion
Source: "..\app\core\*";               DestDir: "{app}\app\core";            Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\app\shared\*";             DestDir: "{app}\app\shared";          Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\app\JobDocs.iconset\*";    DestDir: "{app}\app\JobDocs.iconset"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\app\modules\__init__.py";  DestDir: "{app}\app\modules";         Flags: ignoreversion
Source: "..\app\modules\search\*";     DestDir: "{app}\app\modules\search";  Flags: ignoreversion recursesubdirs createallsubdirs
#else
; Full Python source tree, every module (runs via runtime\pythonw.exe).
Source: "..\app\*";                    DestDir: "{app}\app";                 Flags: ignoreversion recursesubdirs createallsubdirs
#endif

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

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    AddToPath(ExpandConstant('{app}'));

#ifdef KIOSK
    { Drop a marker file the app itself reads at startup to switch into
      read-only (search-only) mode (window title, hidden menu bar, and the
      AppContext persistence guard -- see main.py). The real containment is
      the [Files] selection above: JobDocs Kiosk never has the
      write-capable modules on disk, so deleting this marker unlocks
      nothing that isn't already there. }
    SaveStringToFile(ExpandConstant('{app}\readonly.marker'), 'search-only' + #13#10, False);
#endif
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
      { Must match shared/utils.py's get_config_dir() exactly -- Kiosk uses
        its own "JobDocs Kiosk" subdirectory so uninstalling one variant
        never touches the other's settings/history/search index; they're
        separate installers meant to coexist on one machine. }
#ifdef KIOSK
      ConfigDir := ExpandConstant('{localappdata}\JobDocs Kiosk');
#else
      ConfigDir := ExpandConstant('{localappdata}\JobDocs');
#endif
      if DirExists(ConfigDir) then
        DelTree(ConfigDir, True, True, True);
    end;
  end;
end;
