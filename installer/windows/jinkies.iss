; Inno Setup script for Jinkies
; https://jrsoftware.org/isinfo.php

#define MyAppName "Jinkies"
; MyAppVersion is passed in from build_windows.ps1 via /DMyAppVersion=<ver>
; Fall back to a placeholder if compiled directly without the build script.
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-dev"
#endif
#define MyAppPublisher "SeamusMullan"
#define MyAppURL "https://github.com/SeamusMullan/Jinkies"
#define MyAppExeName "Jinkies.exe"
#define MyAppDescription "Jinkies, my build failed!"

[Setup]
AppId={{A3F2B1C4-7E5D-4F8A-9C2B-1D6E3F0A8B7C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Installer output
OutputDir=..\..\dist
OutputBaseFilename=JinkiesSetup
; Compression
Compression=lzma2
SolidCompression=yes
; Allow per-user (non-admin) or machine-wide (admin) install.
; {autopf} resolves to {localappdata}\Programs for non-admin and to
; {pf} (Program Files) for admin installs.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Architecture: allow install on 64-bit Windows
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Wizard style
WizardStyle=modern
; Use icon if it exists (template path — place icon.ico in assets/)
#if FileExists("..\..\assets\icon.ico")
SetupIconFile=..\..\assets\icon.ico
#endif
; Uninstaller settings
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main executable (built by PyInstaller)
Source: "..\..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu shortcut
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"
; Start Menu uninstall shortcut
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
; Optional desktop icon (only if the "desktopicon" task was selected)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "{#MyAppDescription}"

[Dirs]
; Create the %APPDATA%\jinkies config directory so the app can write on first launch
Name: "{userappdata}\jinkies"

[Run]
; Offer to launch the app after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove the config directory on uninstall (optional — comment out to preserve user data)
; Type: filesandordirs; Name: "{userappdata}\jinkies"
