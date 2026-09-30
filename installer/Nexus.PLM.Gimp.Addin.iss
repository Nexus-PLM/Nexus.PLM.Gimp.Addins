; Inno Setup script for the Nexus PLM plug-in for GIMP.
;
; There is no build step. The plug-in is Python that runs under GIMP's own interpreter, so what
; ships is what is in `plug-in\nexus-plm\`. Compile it with:
;
;   "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" installer\Nexus.PLM.Gimp.Addin.iss
;
; PER-USER, NO ELEVATION. GIMP reads plug-ins from its own installation, which needs admin rights
; and is wiped by the next GIMP update, and from %APPDATA%\GIMP\<version>\plug-ins, which needs
; neither. This installs into the second.
;
; THE FOLDER NAME IS LOAD-BEARING. GIMP 3 only runs a plug-in at plug-ins\<name>\<name>.py - the
; folder and the file share a name. Install it under any other folder and GIMP does not show it,
; and says nothing about why. `tests\test_installer.py` holds the name here against the file in
; plug-in\, because nothing about getting this wrong fails loudly.
;
; THE VERSION FOLDER IS CHOSEN AT INSTALL TIME. GIMP keeps one profile per minor version
; (%APPDATA%\GIMP\3.0, \3.2, ...) and reads plug-ins only from the one that matches the GIMP that
; is running. The newest that exists on this machine is used; see GimpVersionDir below.
;
; WHAT THIS DOES NOT INSTALL: the Nexus PLM tray application, which hosts the Addin Service the
; plug-in talks to on localhost. It comes from Nexus.PLM.WPF.Addins.

#define AppName "Nexus PLM for GIMP"
#define AppPublisher "NexusPLM"

; Keep in step with plug-in\nexus-plm\nexusplm\commands.py VERSION. tests\test_installer.py
; fails when they drift.
#define AppVersion "0.2.0"

; Must match the folder and file name in plug-in\. tests\test_installer.py holds this.
#define PluginName "nexus-plm"

[Setup]
AppId={{7C2D9E41-5B3F-4A8E-B6D1-0F9C3E7A2D54}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
; Nothing is installed here - the plug-in goes into GIMP's own folder - but Inno wants an
; application directory for its uninstall record, so it gets one it will not fill.
DefaultDirName={localappdata}\Programs\Nexus PLM GIMP Addin
DefaultGroupName=Nexus PLM
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=NexusPlmGimpAddinSetup
OutputDir=Output
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; The whole plug-in folder, into plug-ins\nexus-plm under whichever GIMP profile is newest.
; __pycache__ is excluded because a stale compiled file is how an old module goes on being
; imported after its source has changed.
Source: "..\plug-in\{#PluginName}\*"; DestDir: "{code:GimpPluginsDir}\{#PluginName}"; \
  Excludes: "__pycache__,*.pyc"; Flags: recursesubdirs createallsubdirs ignoreversion

[UninstallDelete]
; Only the plug-in's own folder. Its parent holds every other plug-in the user has.
Type: filesandordirs; Name: "{code:GimpPluginsDir}\{#PluginName}"

[Code]

var
  ChosenVersionDir: String;

// The newest GIMP profile under %APPDATA%\GIMP. A profile is created the first time that GIMP
// version runs, so the newest one is the GIMP the user actually uses. Compared as numbers, not
// strings: "3.10" sorts before "3.2" as text and after it as a version.
function NewerVersion(const A, B: String): Boolean;
var
  MajorA, MinorA, MajorB, MinorB, P: Integer;
begin
  P := Pos('.', A);
  MajorA := StrToIntDef(Copy(A, 1, P - 1), 0);
  MinorA := StrToIntDef(Copy(A, P + 1, Length(A)), 0);
  P := Pos('.', B);
  MajorB := StrToIntDef(Copy(B, 1, P - 1), 0);
  MinorB := StrToIntDef(Copy(B, P + 1, Length(B)), 0);
  Result := (MajorA > MajorB) or ((MajorA = MajorB) and (MinorA > MinorB));
end;

function GimpVersionDir(): String;
var
  Root, Best: String;
  Rec: TFindRec;
begin
  Root := ExpandConstant('{userappdata}\GIMP');
  Best := '';
  if FindFirst(Root + '\*', Rec) then
  begin
    try
      repeat
        if ((Rec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0)
           and (Rec.Name <> '.') and (Rec.Name <> '..')
           and (Pos('.', Rec.Name) > 0)
           and ((Best = '') or NewerVersion(Rec.Name, Best)) then
          Best := Rec.Name;
      until not FindNext(Rec);
    finally
      FindClose(Rec);
    end;
  end;
  // No profile at all: GIMP is not installed or has never run. Install for the version this
  // plug-in was written against, so that starting GIMP 3.2 afterwards picks it up.
  if Best = '' then
    Best := '3.2';
  Result := Root + '\' + Best;
end;

// Called by [Files] and [UninstallDelete]. Decided once, so install and uninstall agree.
function GimpPluginsDir(Param: String): String;
begin
  if ChosenVersionDir = '' then
    ChosenVersionDir := GimpVersionDir();
  Result := ChosenVersionDir + '\plug-ins';
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not DirExists(ExpandConstant('{userappdata}\GIMP')) then
    Result := MsgBox(
      'GIMP was not found for this user.' + #13#10#13#10 +
      'Its profile folder does not exist yet, which means it is either not installed or has ' +
      'never been started. The plug-in can still be installed now, for GIMP 3.2, and will ' +
      'appear the first time GIMP runs.' + #13#10#13#10 +
      'Continue?',
      mbConfirmation, MB_YESNO) = IDYES;
end;

// GIMP reads its plug-ins when it starts. Installing underneath a running GIMP leaves the user
// looking at a menu bar with no Nexus PLM on it, and concluding the installer failed.
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not WizardSilent) then
    // A line may not BEGIN with #13#10: the preprocessor reads a leading '#' as a directive
    // and refuses to compile. Keep the line breaks mid-line.
    MsgBox('Nexus PLM is installed for GIMP ' + ExtractFileName(ChosenVersionDir) + '.' + #13#10#13#10 +
           'If GIMP is open, close it and start it again - it reads its plug-ins at startup. ' +
           'The commands are in the Nexus PLM menu.',
           mbInformation, MB_OK);
end;
