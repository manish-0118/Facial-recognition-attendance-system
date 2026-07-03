#define AppName      "Biometric Attendance System"
#define AppShortName "NihareekaAttendance"
#define AppVersion   "1.0.0"
#define AppPublisher "Nihareeka College of Management and Information Technology"
#define AppExeName   "NihareekaAttendance.exe"

[Setup]
AppId={{B3F7A291-4C2D-4E8F-9D1A-6E0C5F2B8D3A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppShortName}
DefaultGroupName={#AppName}
OutputDir=dist\installer
OutputBaseFilename=NihareekaAttendance_Setup
SetupIconFile=assets\favicon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
DisableDirPage=no
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; Main application (PyInstaller one-folder output)
Source: "dist\NihareekaAttendance\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Bundled MariaDB portable (place mariadb\ folder next to dist\ before building)
Source: "mariadb\*"; DestDir: "{app}\mariadb"; Flags: ignoreversion recursesubdirs createallsubdirs


[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Initialise the database on first install (silent, no window)
Filename: "{app}\{#AppExeName}"; Parameters: "--setup-db ""{app}"""; \
  Description: "Initialising database..."; \
  Flags: runhidden waituntilterminated; \
  StatusMsg: "Setting up database, please wait..."

; Launch the app after install finishes
Filename: "{app}\{#AppExeName}"; \
  Description: "Launch {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop the MariaDB server before uninstalling
Filename: "{app}\{#AppExeName}"; Parameters: "--stop-db"; Flags: runhidden waituntilterminated

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
