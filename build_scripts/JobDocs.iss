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
PrivilegesRequiredOverridesAllowed=commandline

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
  ConfigDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if not KeepSettings then
    begin
      ConfigDir := ExpandConstant('{localappdata}\JobDocs');
      if DirExists(ConfigDir) then
        DelTree(ConfigDir, True, True, True);
    end;
  end;
end;
