# CLAUDE.md — Nexus.PLM.Gimp.Addins

The Nexus PLM add-in for GIMP: a Python plug-in with its own **Nexus PLM** menu.

---

## Layout

```
plug-in/
  build.py              installs into GIMP's user plug-ins directory
  nexus-plm/
    nexus-plm.py        entry point - registers one procedure per menu entry
    nexusplm/
      client.py         HTTP to the Addin Service     ] shared with the LibreOffice and
      state.py          path -> item map              ] Inkscape add-ins; no GIMP API in
      identity.py       which item a file is          ] any of them
      navigator.py      folder tree shaping           ]
      menu.py           the menu table - no gi, so tests can read it
      xcf.py            the parasite record, and named text layers
      host.py           the parts that know they are inside GIMP
      commands.py       what each menu entry does
tools/                  developer-only: the template builder plug-in
tests/                  pytest with a fake GIMP; no GIMP needed
```

## Build

```bash
python plug-in/build.py --install
python -m pytest tests/ -q
```

## Rules that are not negotiable

- **The parasite record is the deliverable.** Attributes go into the image's own data model so the
  `.xcf` carries them wherever it goes. Writing values into named text layers is a convenience
  most users will not use - never let a command depend on it.
- **`PARASITE_PERSISTENT` or it never reaches the file.** A parasite without the flag lives only
  while the image is open and vanishes on save, silently. A test pins this.
- **The plug-in must be `plug-ins/<name>/<name>.py`** - folder and file share a name - and
  executable on non-Windows. GIMP skips a plug-in that breaks either rule and says nothing.
- **Uploads write the image, as XCF, to its OWN file** via `host.upload_copy`, and send that path.
  Not a temp copy: `SaveRequest` has one `FilePath` that the service both reads and records as the
  item's `plm_file_path`, so a temp path became the next revision's home (Revise staged rev B under
  `%TEMP%` and opened a second window - measured on the Inkscape add-in, same design). Marc: "it
  must get written to the staging directory." A `.png` cannot carry a parasite, so a non-XCF image
  is written to a sibling `.xcf` of the same name.
- **Revise ups the revision in place.** When the staged file *is* the open image
  (`host.same_file`), `_hand_over` writes the new revision's record into the open image instead of
  launching a second GIMP. A different file - Open from PLM, Search - still opens in a new GIMP.
- **Save As New offers only `xcf.offerable_values`**: filled-in values that are not PLM's own
  (part number, revision, the four stamps). The service merges the offer onto the new revision
  as-is, and a template's blanks wiped `createdBy`/`creationDate` to `""`.
- **The menu is not under Filters.** Nexus PLM is document management, not an image filter; it
  gets a top-level menu like LibreOffice's and OpenOffice's.
- **Standard library only** in `nexusplm/`, plus the `gi` bindings GIMP provides. We do not
  control what is installed in GIMP's Python; `requests` is not there.
- **The service is the only thing this talks to.** Never the Engine, never the vault.
- **A command never leaves a traceback in front of the user.** GIMP shows a plug-in's stderr in
  its Error Console, so stderr is a user interface: warnings are silenced at the entry point and
  `commands.run` turns anything unexpected into a toast.
- `xcf` and `host` take `gimp`/`gio` as arguments so they can be tested with `tests/fakegimp.py`.
  Keep it that way.

## Measured facts worth not re-learning

- A **persistent parasite survives a save/reload round trip** through XCF, value intact.
- GIMP **sorts a menu's entries alphabetically**; the order of `MENU` is documentation.
- A GIMP `bin` directory contains `gimp-debug-tool.exe`, `gimp-test-clipboard.exe` and
  `gimp-script-fu-interpreter-3.0.exe` alongside `gimp-3.2.exe`. "Everything starting with
  `gimp-`, sorted, take the last" picks **the clipboard tester** - Open from PLM launched it, no
  window appeared, and the command reported success. `host.gimp_executable` matches an anchored
  pattern now, and six tests hold it.
- A plug-in runs as a **fresh process per invocation**, so editing it takes effect without
  restarting GIMP - but the *menu* is read at startup, so a new command needs a restart.

## Installer

`installer/Nexus.PLM.Gimp.Addin.iss` - Inno Setup, per-user, no elevation. Compile with ISCC;
`tests/test_installer.py` holds it against the source (version, plug-in name, payload, uninstall
scope). It installs into the plug-ins folder of the **newest** `%APPDATA%\GIMP\<version>`
profile, chosen at install time. `build.py --install` remains the developer path.

One Inno trap: a `[Code]` line may not *begin* with `#13#10` - the preprocessor reads a leading
`#` as a directive and refuses to compile.

## Still to do

- **All 21 commands driven end to end on the installed plug-in (29 Sep 2026)**, on the build that
  carried the four fixes ported from the Inkscape sweep (PR #6). Service-side observations are in
  Nexus.PLM.Inkscape.Addins PR #8.
- Attributes do not survive **export** to PNG/JPEG. XMP would fix that; nobody has asked yet.

## Measured while driving

- **GIMP is single-instance.** `gimp-3.2.exe <file>` hands the file to the running GIMP, which
  opens it as another image in the same process - `host.open_document` does not get a second GIMP
  on Windows, and does not need one. The plug-in acts on the image whose window the menu was used in.
- `Gimp.file_save` to the image's own file (Save to PLM) leaves the image **clean** - the title
  loses its `*`, as after a real Save.
- Revise in place: the record is written into the open image; "wrote 7 value(s), 0 shown" is
  normal for an image with no text layers named for a key.
