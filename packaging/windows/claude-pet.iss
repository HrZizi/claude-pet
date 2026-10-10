; Inno Setup script (https://jrsoftware.org/isinfo.php). Build with:  python scripts/build.py --installer
; Installs per-user (no admin rights) to %LOCALAPPDATA%\Programs\ClaudePet, which also keeps the Claude Code
; hook command free of spaces.
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6F1A4D52-3C1E-4B0B-9E55-7A1C3D2B8E10}
AppName=Claude Pet
AppVersion={#AppVersion}
AppPublisher=claude-pet contributors
AppPublisherURL=https://github.com/OWNER/claude-pet
DefaultDirName={localappdata}\Programs\ClaudePet
DefaultGroupName=Claude Pet
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=ClaudePet-Setup-{#AppVersion}
SetupIconFile=..\..\assets\icon.ico
UninstallDisplayIcon={app}\ClaudePet.exe
LicenseFile=..\..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Tasks]
Name: "connect"; Description: "Connect to Claude Code (adds hooks to ~/.claude/settings.json, with a backup)"; GroupDescription: "Setup:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\ClaudePet\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Claude Pet"; Filename: "{app}\ClaudePet.exe"
Name: "{autodesktop}\Claude Pet"; Filename: "{app}\ClaudePet.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\claude-pet-cli.exe"; Parameters: "install"; Flags: runhidden; Tasks: connect
Filename: "{app}\ClaudePet.exe"; Description: "Launch Claude Pet"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\claude-pet-cli.exe"; Parameters: "uninstall"; Flags: runhidden; RunOnceId: "RemoveHooks"
