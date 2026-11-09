; Instalador Windows do Tunel Clientes (Inno Setup 6). Gerado pelo build.py.
; Só para o usuário atual, sem administrador. Dados e senha ficam no perfil do usuário e não são apagados.

#ifndef Versao
  #define Versao "0.0.0"
#endif

[Setup]
AppId={{2E7C4A90-5B1D-4F3E-9C8A-61D0B7E5F342}
AppName=Tunel Clientes
AppVersion={#Versao}
AppPublisher=CAM
DefaultDirName={localappdata}\Programs\Tunel Clientes
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=tunel-clientes-{#Versao}-windows-setup
UninstallDisplayIcon={app}\Tunel Clientes.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktop"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "..\dist\Tunel Clientes\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Tunel Clientes"; Filename: "{app}\Tunel Clientes.exe"
Name: "{autodesktop}\Tunel Clientes"; Filename: "{app}\Tunel Clientes.exe"; Tasks: desktop

[Run]
Filename: "{app}\Tunel Clientes.exe"; Description: "Abrir o Tunel Clientes"; Flags: postinstall nowait skipifsilent
