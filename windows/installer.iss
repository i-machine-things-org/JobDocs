; JobDocs Inno Setup Installer Script
; Creates a Windows installer for JobDocs
; Requires Inno Setup: https://jrsoftware.org/isinfo.php

; VERSION define passed from build script via /DVERSION=
; Default to 0.0.0 if not provided
; VERSION can include stage identifiers (e.g., "0.2.0-alpha")
; Must be in format "major.minor.patch" or "major.minor.patch-stage"
#ifndef VERSION
  #define VERSION "0.0.0"
#endif

; Extract numeric part for VersionInfoVersion (must be 4-part: X.X.X.0)
; This strips any "-alpha", "-beta", etc. suffixes
#define NumericVersion Copy(VERSION, 1, Pos("-", VERSION + "-") - 1)

[Setup]
; Application information
AppName=JobDocs
AppVersion={#VERSION}
AppPublisher=JobDocs Developers
AppPublisherURL=https://github.com/i-machine-things/JobDocs
AppSupportURL=https://github.com/i-machine-things/JobDocs/issues
AppUpdatesURL=https://github.com/i-machine-things/JobDocs/releases
DefaultDirName={autopf}\JobDocs
DefaultGroupName=JobDocs
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=..\
OutputBaseFilename=JobDocs-Setup-{#VERSION}
SetupIconFile=..\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Version information
VersionInfoVersion={#NumericVersion}.0
VersionInfoCompany=JobDocs Developers
VersionInfoDescription=JobDocs Installer
VersionInfoCopyright=Copyright (C) 2024 JobDocs Developers
VersionInfoProductName=JobDocs
VersionInfoProductVersion={#VERSION}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "..\dist\jobdocs.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "..\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\JobDocs"; Filename: "{app}\jobdocs.exe"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,JobDocs}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\JobDocs"; Filename: "{app}\jobdocs.exe"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\jobdocs.exe"; Description: "Launch JobDocs now"; Flags: nowait postinstall skipifsilent

[Messages]
WelcomeLabel2=This will install JobDocs on your computer.%n%nJobDocs helps you manage blueprint files and customer job folders.%n%nClick Next to continue.
FinishedLabel=JobDocs has been installed successfully!%n%nYou can now find JobDocs in the Start Menu and on your Desktop (if selected).%n%nClick Finish to complete the installation.

[Registry]
Root: HKCU; Subkey: "Software\JobDocs"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
