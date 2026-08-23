; DOOF v0.2 Alpha — Inno Setup Script
; Run this file in Inno Setup to generate "DOOF Setup.exe"
; Prerequisite: You must have built the DOOF.exe using `packaging\build.bat` first.

[Setup]
AppName=DOOF
AppVersion=0.2 Alpha
AppPublisher=DOOF Network
DefaultDirName={autopf}\DOOF
DefaultGroupName=DOOF
OutputDir=..\dist
OutputBaseFilename=DOOF Setup
SetupIconFile=..\assets\doof.ico
UninstallDisplayIcon={app}\DOOF.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
; First launch login & auto-updater ready (hooks for future expansion)

[Files]
Source: "..\dist\DOOF\DOOF.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\DOOF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\DOOF"; Filename: "{app}\DOOF.exe"
Name: "{autodesktop}\DOOF"; Filename: "{app}\DOOF.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\DOOF.exe"; Description: "Launch DOOF"; Flags: nowait postinstall skipifsilent

[Code]
// First launch login logic hook (stub)
procedure InitializeWizard;
begin
  // E.g., check registry or local appdata to see if user has logged in before.
end;
