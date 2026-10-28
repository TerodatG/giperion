; Giperion/packaging/windows/giperion.iss                            v001
; Inno Setup: установщик Windows для one-dir сборки PyInstaller.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

#ifndef SourceDir
  #define SourceDir "..\..\dist\Giperion"
#endif

#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{8F1C2E44-5B6D-4A2E-9C71-3D2B7A6F1E20}
AppName=Giperion
AppVersion={#AppVersion}
AppPublisher=Giperion
DefaultDirName={autopf}\Giperion
DefaultGroupName=Giperion
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=Giperion-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Giperion"; Filename: "{app}\Giperion.exe"
Name: "{autodesktop}\Giperion"; Filename: "{app}\Giperion.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Giperion.exe"; Description: "{cm:LaunchProgram,Giperion}"; Flags: nowait postinstall skipifsilent
