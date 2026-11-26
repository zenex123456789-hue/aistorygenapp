; Inno Setup script. Built by .github/workflows/windows-installer.yml (needs dist\AIStoryFactory from PyInstaller).
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6E1B7C0E-5C1D-4B63-9D6E-7A57F0A9C1D2}
AppName=AI Story Factory
AppVersion={#AppVersion}
AppPublisher=AI Story Factory
DefaultDirName={autopf}\AI Story Factory
DefaultGroupName=AI Story Factory
PrivilegesRequired=lowest
OutputDir=..\installer-out
OutputBaseFilename=AI-Story-Factory-Setup
SetupIconFile=app.ico
UninstallDisplayIcon={app}\AIStoryFactory.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\AIStoryFactory\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\AI Story Factory"; Filename: "{app}\AIStoryFactory.exe"
Name: "{autodesktop}\AI Story Factory"; Filename: "{app}\AIStoryFactory.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AIStoryFactory.exe"; Description: "Launch AI Story Factory"; Flags: nowait postinstall skipifsilent

; Your projects and API keys live in %LOCALAPPDATA%\AIStoryFactory and are NOT removed on uninstall.
