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
; plugins/ is never removed on uninstall so user-installed plugins survive upgrades
Name: "{app}\plugins"; Flags: uninsneveruninstall

[Files]
; Launcher executable
Source: "..\JobDocs.exe";    DestDir: "{app}"; Flags: ignoreversion

; Python source tree (runs via runtime\pythonw.exe)
Source: "..\app\*";          DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs

; Embedded Python 3.12 runtime with pre-installed dependencies
Source: "..\runtime\*";      DestDir: "{app}\runtime"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}";                          Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}";    Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";                    Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
