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
- **Uploads send a temp `.xcf`**, via `host.upload_copy`, never the user's own file. Saving over
  their file is a side effect nobody asked a PLM command to have, and a `.png` cannot carry a
  parasite at all.
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

## Still to do

- Only New from Template, and the commands it calls, have been driven end to end.
- No installer: `build.py --install` is a developer script, and nothing user-facing may depend on
  one.
- Attributes do not survive **export** to PNG/JPEG. XMP would fix that; nobody has asked yet.
