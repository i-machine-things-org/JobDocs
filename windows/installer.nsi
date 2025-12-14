; JobDocs NSIS Installer Script
; Creates a Windows installer for JobDocs

;--------------------------------
; Include Modern UI

  !include "MUI2.nsh"
  !include "LogicLib.nsh"

;--------------------------------
; General

  ; Name and file
  Name "JobDocs"
  OutFile "JobDocs-Setup-0.2.0-alpha.exe"
  Unicode True

  ; Default installation folder
  InstallDir "$PROGRAMFILES64\JobDocs"

  ; Get installation folder from registry if available
  InstallDirRegKey HKLM "Software\JobDocs" ""

  ; Request application privileges for Windows Vista+
  RequestExecutionLevel admin

;--------------------------------
; Variables

  Var StartMenuFolder

;--------------------------------
; Interface Settings

  !define MUI_ABORTWARNING
  !define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
  !define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

;--------------------------------
; Pages

  !insertmacro MUI_PAGE_LICENSE "LICENSE"
  !insertmacro MUI_PAGE_COMPONENTS
  !insertmacro MUI_PAGE_DIRECTORY

  ; Start Menu Folder Page Configuration
  !define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKCU"
  !define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\JobDocs"
  !define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"

  !insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder

  !insertmacro MUI_PAGE_INSTFILES

  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES

;--------------------------------
; Languages

  !insertmacro MUI_LANGUAGE "English"

;--------------------------------
; Installer Sections

Section "JobDocs" SecMain

  SetOutPath "$INSTDIR"

  ; Add files
  File "dist\jobdocs.exe"
  File "LICENSE"
  File "README.md"

  ; Store installation folder
  WriteRegStr HKLM "Software\JobDocs" "" $INSTDIR

  ; Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Add to Add/Remove Programs
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JobDocs" \
                   "DisplayName" "JobDocs"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JobDocs" \
                   "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JobDocs" \
                   "DisplayIcon" "$INSTDIR\jobdocs.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JobDocs" \
                   "Publisher" "JobDocs Developers"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JobDocs" \
                   "DisplayVersion" "0.2.0-alpha"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JobDocs" \
                   "URLInfoAbout" "https://github.com/i-machine-things/JobDocs"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JobDocs" \
                   "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JobDocs" \
                   "NoRepair" 1

  ; Create start menu shortcuts
  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application

    CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
    CreateShortcut "$SMPROGRAMS\$StartMenuFolder\JobDocs.lnk" "$INSTDIR\jobdocs.exe" "" "$INSTDIR\jobdocs.exe" 0
    CreateShortcut "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

  !insertmacro MUI_STARTMENU_WRITE_END

SectionEnd

;--------------------------------
; Optional Desktop Shortcut Section

Section "Desktop Shortcut" SecDesktop

  CreateShortcut "$DESKTOP\JobDocs.lnk" "$INSTDIR\jobdocs.exe" "" "$INSTDIR\jobdocs.exe" 0

SectionEnd

;--------------------------------
; Descriptions

  ; Language strings
  LangString DESC_SecMain ${LANG_ENGLISH} "JobDocs main application (required)"
  LangString DESC_SecDesktop ${LANG_ENGLISH} "Create a shortcut on the desktop"

  ; Assign language strings to sections
  !insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} $(DESC_SecMain)
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} $(DESC_SecDesktop)
  !insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
; Uninstaller Section

Section "Uninstall"

  ; Remove files
  Delete "$INSTDIR\jobdocs.exe"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\Uninstall.exe"

  ; Remove directories
  RMDir "$INSTDIR"

  ; Remove Start Menu shortcuts
  !insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder

  Delete "$SMPROGRAMS\$StartMenuFolder\JobDocs.lnk"
  Delete "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk"
  RMDir "$SMPROGRAMS\$StartMenuFolder"

  ; Remove desktop shortcut if it exists
  ${If} ${FileExists} "$DESKTOP\JobDocs.lnk"
    Delete "$DESKTOP\JobDocs.lnk"
  ${EndIf}

  ; Remove registry keys
  DeleteRegKey /ifempty HKLM "Software\JobDocs"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JobDocs"

SectionEnd
