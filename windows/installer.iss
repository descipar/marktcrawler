; Inno Setup Skript für Marktcrawler
; Wird vom GitHub Actions Windows-Runner erzeugt.
; Manuell bauen: iscc windows\installer.iss  (aus Projekt-Root)

#define AppName      "Marktcrawler"
#define AppVersion   "1.2.0"
#define AppPublisher "Marktcrawler"
#define AppExeName   "Marktcrawler.exe"
#define AppURL       "https://github.com/descipar/marktcrawler"

[Setup]
AppId={{8F4A2C1E-3D7B-4F9A-B2E6-1A5C8D0F3E7B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=windows\Output
OutputBaseFilename=MarktcrawlerSetup
SetupIconFile=windows\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Zusätzliche Symbole:"; Flags: checked

[Files]
Source: "dist\Marktcrawler\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";               Filename: "{app}\{#AppExeName}"
Name: "{group}\{#AppName} deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";          Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{#AppName} jetzt starten"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Prozess beenden bevor Dateien gelöscht werden
Filename: "taskkill.exe"; Parameters: "/f /im {#AppExeName}"; Flags: runhidden; RunOnceId: "KillApp"
