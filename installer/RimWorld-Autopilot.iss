#define AppName "RimWorld Autopilot"
; AppVersion is supplied by Build-GUI.ps1 from the repository VERSION file.
#define AppExeName "RimWorld-Autopilot.exe"

[Setup]
AppId={{D7D7334A-EBC6-4D25-8D0E-71EC2BF584B9}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=RimWorld Autopilot contributors
AppPublisherURL=https://github.com/Georgy-hook/rimworld-autopilot
AppSupportURL=https://github.com/Georgy-hook/rimworld-autopilot/issues
AppUpdatesURL=https://github.com/Georgy-hook/rimworld-autopilot/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=RimWorld-Autopilot-{#AppVersion}-Setup
SetupIconFile=..\assets\gui\autopilot.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}
Uninstallable=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
PrivilegesRequired=admin
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern dynamic windows11 includetitlebar
WizardSizePercent=110
WizardImageFile=..\assets\gui\autopilot-installer-portrait.png
WizardImageFileDynamicDark=..\assets\gui\autopilot-installer-portrait.png
WizardSmallImageFile=..\assets\gui\autopilot-emblem.png
WizardSmallImageFileDynamicDark=..\assets\gui\autopilot-emblem.png
WizardImageBackColor=$090B12
WizardImageBackColorDynamicDark=$090B12
WizardSmallImageBackColor=$090B12
WizardSmallImageBackColorDynamicDark=$090B12
WizardKeepAspectRatio=yes
CloseApplications=yes
RestartApplications=no
RestartIfNeededByRun=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[CustomMessages]
english.AdditionalIcons=Shortcuts
english.DesktopIcon=Create a desktop shortcut
english.ConfigureNow=Configure Python, the local model and the RimWorld mod now
english.LaunchNow=Open RimWorld Autopilot
russian.AdditionalIcons=Ярлыки
russian.DesktopIcon=Добавить ярлык на рабочий стол
russian.ConfigureNow=Настроить Python, локальную модель и мод RimWorld сейчас
russian.LaunchNow=Открыть RimWorld Autopilot

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
Type: files; Name: "{app}\Laya-Setup.exe"
; Remove files installed by older broad payloads without touching configuration,
; model environments, logs, or user preferences.
Type: filesandordirs; Name: "{app}\assets"
Type: filesandordirs; Name: "{app}\docs"
Type: filesandordirs; Name: "{app}\laya_gui"
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\vendor\RIMAPI\Source"
Type: filesandordirs; Name: "{app}\vendor\RIMAPI\1.5"
Type: files; Name: "{app}\vendor\RIMAPI\UPSTREAM-README.md"
Type: files; Name: "{app}\vendor\RIMAPI\1.6\Assemblies\RIMAPI.pdb"
Type: files; Name: "{app}\ARCHITECTURE.md"
Type: files; Name: "{app}\Build-GUI.ps1"
Type: files; Name: "{app}\CONTRIBUTING.md"
Type: files; Name: "{app}\CUSTOM-RIMAPI.md"
Type: files; Name: "{app}\DIRECTION_AUDIT.md"
Type: files; Name: "{app}\GUI.md"
Type: files; Name: "{app}\Install.ps1"
Type: files; Name: "{app}\PLAYTEST_REPORT.md"
Type: files; Name: "{app}\README.md"
Type: files; Name: "{app}\RELEASE_NOTES.md"
Type: files; Name: "{app}\RIMAPI_UPSTREAM_COMMIT"
Type: files; Name: "{app}\SECURITY.md"
Type: files; Name: "{app}\Start-Autonomous.ps1"
Type: files; Name: "{app}\Start-Preview.ps1"
Type: files; Name: "{app}\VERSION"
Type: files; Name: "{app}\autopilot_control.py"
Type: files; Name: "{app}\autopilot_setup.py"
Type: files; Name: "{app}\design-qa.md"
Type: files; Name: "{app}\install_payload.py"
Type: files; Name: "{app}\laya_control.py"
Type: files; Name: "{app}\laya_setup.py"
Type: files; Name: "{app}\requirements-build.txt"
Type: files; Name: "{app}\requirements-promo.txt"

[Files]
Source: "..\dist\RimWorld-Autopilot-{#AppVersion}-install\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\RimWorld-Autopilot-Setup.exe"; Parameters: "--installed-dir ""{app}"""; Description: "{cm:ConfigureNow}"; Flags: postinstall skipifsilent runascurrentuser waituntilterminated
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchNow}"; WorkingDir: "{app}"; Flags: postinstall skipifsilent unchecked nowait runasoriginaluser
