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
; dependencies need. The Job, Quote, and Bulk *module tabs* are never
; copied, so there is no write-capable module code to unlock -- see
; main.py's _is_readonly_install(). core\* is copied in full, which does
; include settings_dialog.py -- the Settings dialog and its File menu
; entry remain present and reachable in a Kiosk install; any changes just
; don't persist, blocked separately by readonly_mode's save_settings()/
; save_history() guards (core/app_context.py), not by omitting this code
; (CodeRabbit, PR #317 promotion review).
Source: "..\app\main.py";              DestDir: "{app}\app";                 Flags: ignoreversion
Source: "..\app\core\*";               DestDir: "{app}\app\core";            Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\app\shared\*";             DestDir: "{app}\app\shared";          Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\app\JobDocs.iconset\*";    DestDir: "{app}\app\JobDocs.iconset"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\app\modules\__init__.py";  DestDir: "{app}\app\modules";         Flags: ignoreversion
Source: "..\app\modules\search\*";     DestDir: "{app}\app\modules\search";  Flags: ignoreversion recursesubdirs createallsubdirs
; Build-time Kiosk identity: baked into the installer payload here, not
; written by a post-install script, so it can't be deleted the way
; readonly.marker used to be (CodeRabbit, PR #315). shared.utils.
; is_kiosk_install() checks for its presence -- the single source of truth
; for get_config_dir()'s Kiosk-suffixed directory and main.py's read-only
; persistence guard, so both stay correct even if a user goes looking for
; something to delete to "unlock" the app.
Source: "kiosk_build.marker";          DestDir: "{app}\app\shared";          Flags: ignoreversion
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
#ifdef KIOSK
  KioskDirsPage: TInputDirWizardPage;
#endif

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

#ifdef KIOSK
procedure InitializeWizard();
{ JobDocs Kiosk doesn't ship the first-run OOBE wizard (a write-capable
  admin tool, excluded from [Files] above) -- its search directories are
  configured here instead, once, at install time. The app's own Settings
  dialog is still present (see the [Files] comment above); its writes are
  blocked by readonly_mode, not by exclusion. }
begin
  KioskDirsPage := CreateInputDirPage(wpSelectDir,
    'Job Data Locations', 'Where should JobDocs Kiosk search for jobs?',
    'Enter the network paths for customer job folders and blueprint files. ' +
    'Ask your JobDocs administrator if you''re not sure. The ITAR fields are ' +
    'optional -- leave blank if this site doesn''t use them. You can change ' +
    'these later by re-running this installer.',
    False, '');
  KioskDirsPage.Add('Customer Files Directory:');
  KioskDirsPage.Add('ITAR Customer Files Directory (optional):');
  KioskDirsPage.Add('Blueprints Directory:');
  KioskDirsPage.Add('ITAR Blueprints Directory (optional):');

  { Pre-fill from a previous install of this same Kiosk product, if updating
    or reinstalling -- SetPreviousData below persists these in the registry
    keyed by AppId, independent of the app dir's kiosk_dirs.json file. }
  KioskDirsPage.Values[0] := GetPreviousData('CustomerFilesDir', '');
  KioskDirsPage.Values[1] := GetPreviousData('ItarCustomerFilesDir', '');
  KioskDirsPage.Values[2] := GetPreviousData('BlueprintsDir', '');
  KioskDirsPage.Values[3] := GetPreviousData('ItarBlueprintsDir', '');
end;

procedure RegisterPreviousData(PreviousDataKey: Integer);
begin
  SetPreviousData(PreviousDataKey, 'CustomerFilesDir', KioskDirsPage.Values[0]);
  SetPreviousData(PreviousDataKey, 'ItarCustomerFilesDir', KioskDirsPage.Values[1]);
  SetPreviousData(PreviousDataKey, 'BlueprintsDir', KioskDirsPage.Values[2]);
  SetPreviousData(PreviousDataKey, 'ItarBlueprintsDir', KioskDirsPage.Values[3]);
end;

function JSONEscape(S: String): String;
var
  I: Integer;
  C: Char;
begin
  Result := '';
  for I := 1 to Length(S) do
  begin
    C := S[I];
    if (C = '\') or (C = '"') then
      Result := Result + '\' + C
    else
      Result := Result + C;
  end;
end;
#endif

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    AddToPath(ExpandConstant('{app}'));

#ifdef KIOSK
    { main.py's AppContext.load_settings() reads this and overrides the
      four directory settings on every launch -- the actual source of
      truth for a Kiosk install, since it has no UI to edit settings.json
      itself. See MainWindow._apply_kiosk_dirs_override(). }
    SaveStringToFile(ExpandConstant('{app}\kiosk_dirs.json'),
      '{' + #13#10 +
      '  "customer_files_dir": "' + JSONEscape(KioskDirsPage.Values[0]) + '",' + #13#10 +
      '  "itar_customer_files_dir": "' + JSONEscape(KioskDirsPage.Values[1]) + '",' + #13#10 +
      '  "blueprints_dir": "' + JSONEscape(KioskDirsPage.Values[2]) + '",' + #13#10 +
      '  "itar_blueprints_dir": "' + JSONEscape(KioskDirsPage.Values[3]) + '"' + #13#10 +
      '}' + #13#10,
      False);
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
