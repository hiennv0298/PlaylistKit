; Inno Setup 6 script for PlaylistKit. Built by scripts\build.ps1 after PyInstaller.
; Installs per user (no admin) into %LOCALAPPDATA%\Programs\PlaylistKit.

#ifndef AppVersion
  #define AppVersion "0.1.2"
#endif

[Setup]
AppId={{4F7A2C19-8D3E-4B6A-A1F5-2E9C7B0D6A43}
AppName=PlaylistKit
AppVersion={#AppVersion}
AppPublisher=hiennv0298
AppComments=Find songs by genre, remix them into one playlist and make the YouTube video
DefaultDirName={localappdata}\Programs\PlaylistKit
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=PlaylistKit-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=yes
WizardStyle=modern
SetupIconFile=..\src\playlistkit\webui\playlistkit.ico
UninstallDisplayIcon={app}\PlaylistKitApp.exe
UninstallDisplayName=PlaylistKit

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "addtopath"; Description: "Add PlaylistKit to PATH (lets you type 'playlistkit' in cmd)"; GroupDescription: "Command line:"

[Files]
Source: "..\dist\PlaylistKit\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PlaylistKit"; Filename: "{app}\PlaylistKitApp.exe"
Name: "{autodesktop}\PlaylistKit"; Filename: "{app}\PlaylistKitApp.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
  ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))

[Run]
Filename: "{app}\PlaylistKitApp.exe"; Description: "Open PlaylistKit now"; Flags: postinstall nowait skipifsilent
; The in-app updater runs this installer with /VERYSILENT /RELAUNCH=1: reopen PlaylistKit when done.
Filename: "{app}\PlaylistKitApp.exe"; Flags: nowait; Check: RelaunchRequested

[Code]
function RelaunchRequested: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;

function NeedsAddPath(Dir: string): Boolean;
var
  Paths: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Paths) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Paths) + ';') = 0;
end;

procedure RemoveFromPath(Dir: string);
var
  Paths: string;
  P: Integer;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Paths) then
    exit;
  P := Pos(';' + Uppercase(Dir), Uppercase(Paths));
  if P > 0 then
  begin
    Delete(Paths, P, Length(Dir) + 1);
    RegWriteExpandStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Paths);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemoveFromPath(ExpandConstant('{app}'));
end;
