; JobDocs Inno Setup Script
; This creates a Windows installer for JobDocs

#define UseIcon
#define MyAppName "JobDocs"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "i-machine-things"
#define MyAppURL "https://github.com/i-machine-things/JobDocs"
#define MyAppExeName "JobDocs.exe"
#define MyAppDescription "Blueprint and customer file management tool"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
AppId={{E8A9F3C1-7B2D-4F6E-9A3C-1D8E5F2B7C4A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppComments={#MyAppDescription}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE
InfoBeforeFile=..\README.md
OutputDir=..\installer_output
OutputBaseFilename=JobDocs-{#MyAppVersion}-Setup
#ifdef UseIcon
SetupIconFile=icon.ico
#endif
Compression=lzma2/ultra64
InternalCompressLevel=ultra64
SolidCompression=yes
WizardStyle=modern
WizardImageFile=compiler:WizModernImage-IS.bmp
WizardSmallImageFile=compiler:WizModernSmallImage-IS.bmp
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
ChangesAssociations=no
DisableProgramGroupPage=no
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppDescription}
VersionInfoTextVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Registry]
; Optional: Add to Windows "Open With" context menu for PDF files
Root: HKCR; Subkey: "Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""; Flags: uninsdeletekey
Root: HKCR; Subkey: "Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey

[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%n{#MyAppDescription}%n%nIt is recommended that you close all other applications before continuing.

[Code]
var
  DataDirPage: TInputDirWizardPage;

procedure InitializeWizard;
begin
  // Create a custom page for selecting data directories
  DataDirPage := CreateInputDirPage(wpSelectDir,
    'Select Data Directories', 'Where should JobDocs store your files?',
    'Select the folders where you want to store blueprints and customer files, then click Next.',
    False, '');

  // Add directory prompts
  DataDirPage.Add('Blueprints Directory:');
  DataDirPage.Add('Customer Files Directory:');

  // Set default values
  DataDirPage.Values[0] := ExpandConstant('{userdocs}\JobDocs\Blueprints');
  DataDirPage.Values[1] := ExpandConstant('{userdocs}\JobDocs\CustomerFiles');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  // Make the data directory page optional (user can skip)
  Result := False;
end;

function EscapeJsonPath(Path: string): string;
begin
  // Replace backslashes with forward slashes for JSON
  Result := Path;
  StringChangeEx(Result, '\', '/', True);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigFile: string;
  ConfigContent: string;
begin
  if CurStep = ssPostInstall then
  begin
    // Create initial config with user's directory preferences
    ConfigFile := ExpandConstant('{localappdata}\JobDocs\settings.json');

    // Create config directory if it doesn't exist
    ForceDirectories(ExtractFileDir(ConfigFile));

    // Create basic config file
    ConfigContent := '{' + #13#10;
    ConfigContent := ConfigContent + '  "blueprints_dir": "' + EscapeJsonPath(AddBackslash(DataDirPage.Values[0])) + '",' + #13#10;
    ConfigContent := ConfigContent + '  "customer_files_dir": "' + EscapeJsonPath(AddBackslash(DataDirPage.Values[1])) + '",' + #13#10;
    ConfigContent := ConfigContent + '  "itar_blueprints_dir": "",' + #13#10;
    ConfigContent := ConfigContent + '  "itar_customer_files_dir": "",' + #13#10;
    ConfigContent := ConfigContent + '  "link_type": "hard",' + #13#10;
    ConfigContent := ConfigContent + '  "blueprint_extensions": [".pdf", ".dwg", ".dxf", ".step", ".stp"],' + #13#10;
    ConfigContent := ConfigContent + '  "allow_duplicate_jobs": false,' + #13#10;
    ConfigContent := ConfigContent + '  "ui_style": "Fusion"' + #13#10;
    ConfigContent := ConfigContent + '}';

    // Save config file if it doesn't exist
    if not FileExists(ConfigFile) then
    begin
      SaveStringToFile(ConfigFile, ConfigContent, False);

      // Create the directories
      ForceDirectories(DataDirPage.Values[0]);
      ForceDirectories(DataDirPage.Values[1]);
    end;
  end;
end;
