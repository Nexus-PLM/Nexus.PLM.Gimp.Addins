# Nexus PLM for GIMP — developer guide

How the plug-in is built, how to change it safely, and what GIMP does differently. Every
"measured" fact below was measured on GIMP 3.2.6 and cost something to learn.

## Architecture in one paragraph

GIMP 3 loads a Python plug-in by running `plug-ins/<name>/<name>.py` and asking its `Gimp.PlugIn`
subclass which procedures it provides; each procedure has a menu label and path. This add-in's
`nexus-plm.py` answers with twenty-one procedures — one per row of the table in
`nexusplm/menu.py` — all under `<Image>/Nexus PLM/` and all dispatching to `commands.run(name,
image)`. A plug-in runs as a **fresh process per invocation**, holding the live `Gimp.Image`.
Everything that talks HTTP is in `nexusplm/client.py`; everything that touches the image's
record is in `nexusplm/xcf.py`; everything that knows it is inside GIMP is in `nexusplm/host.py`.
Nothing else imports `gi`, which is why 77 tests run under plain Python against
`tests/fakegimp.py`.

```
plug-in/
  build.py                copies plug-in/nexus-plm into %APPDATA%\GIMP\<version>\plug-ins
  nexus-plm/
    nexus-plm.py          the Gimp.PlugIn: do_query_procedures / do_create_procedure / _run
    nexusplm/
      menu.py             MENU table, MENU_PATH, procedure names - no gi
      commands.py         one function per command; Context; COMMANDS; run()
      xcf.py              read_values / write_values / offerable_values / write_into_file / draw_values
      host.py             document_path / upload_copy / same_file / open_document / gimp_executable / say / log
      client.py           Client: one method per service endpoint (shared with Inkscape and QGIS)
      state.py            the path → item map, %APPDATA%\NexusPLM\gimp-documents.json (shared)
      identity.py         which item a file is: the map first, then /plm/state (shared)
      navigator.py        folder tree shaping (shared)
tools/nexus-plm-build-template/   a GIMP plug-in that writes dist/GIMP Image.xcf
tests/                    fakegimp.py, test_commands, test_xcf, test_host, test_installer
installer/                Inno Setup script
```

## The one rule everything follows

**The plug-in talks only to the Addin Service** (`http://localhost:5100`), never to the Engine or
the vault. The service owns the session, every dialog and every toast, and it enumerates no hosts:
this add-in declares `HOST_NAME = "GIMP"` and `FILE_EXTENSIONS = ".xcf"` with each request. If a
change here seems to need a service change, stop — it usually means the add-in should be declaring
something instead.

## The record

`xcf.py` keeps PLM's values in an image **parasite** named `nexus-plm/attributes`, a JSON object,
attached with `PARASITE_PERSISTENT` (`1`) — the flag is what makes GIMP write it into the file.

`write_values(image, values, gimp)` merges into the existing record, re-attaches the parasite and
writes any value the image is set up to show — a **text layer named for the key** — returning
`(recorded, drawn)`. `write_into_file(path, values, gimp, gio)` loads a file GIMP has not opened,
writes the record, saves and deletes the image: this is how a staged file gets its values before
GIMP opens it. `offerable_values(image)` is what Save As New offers as the new item's defaults:
filled-in values only, never the server's own keys.

`gimp` and `gio` are **passed in**, not imported, so the same code runs against the fake in tests.
Keep it that way.

## The command shape

Every command is `def name(context)` and returns `None`:

```python
def check_in(context):
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.check_in(item_id, _to_upload(context))
    if not answer.get("success"):
        _refused(context, answer, "Check In")
```

- `_to_upload` → `host.upload_copy`: `Gimp.file_save` of the live image, as XCF, to its **own
  file** (a non-XCF image to a sibling `.xcf`), returning that path. Never a temp copy — the
  service records the path as the item's home.
- `_hand_over(context, answer)`: remember the item, write values into the staged file, then either
  write the record into the **open image** (when the staged file is this image — Revise) or start
  GIMP on the file (which, GIMP being single-instance, opens it in the running GIMP).
- `_apply(context, answer)`: write returned `attribute_mappings` into the open image.
- `run(name, image)`: logs, turns any exception into a toast, lets only `ServiceUnavailable`
  escape for the entry point to put in GIMP's error console.

### Adding a command

1. Add `("my-command", "My Command...")` to `MENU` in `menu.py`.
2. Add `def my_command(context)` in `commands.py` and register it in `COMMANDS`.
3. Add the client method if the service endpoint is new — shapes from the service's
   `PlmModels.cs`, not guessed.
4. `python plug-in/build.py --install` and **restart GIMP** (the menu is read at startup).
5. `TestTheMenuAndTheCommandsAgree` fails until table and dispatch agree.

## Things GIMP does differently (all measured)

| | Consequence |
|---|---|
| A plug-in must be `plug-ins/<name>/<name>.py`, executable off Windows. | `build.py` and the installer get the name right; a test holds it. |
| Plug-ins land under Filters by default. | `MENU_PATH = "<Image>/Nexus PLM/"` makes a top-level menu. GIMP sorts it alphabetically. |
| A fresh process per invocation, menu read at startup. | Edits take effect at once; a new command needs a restart. |
| `bin/` holds `gimp-debug-tool.exe`, `gimp-test-clipboard.exe`… beside `gimp-3.2.exe`. | `gimp_executable` matches `^gimp(-\d+(\.\d+)*)?(\.exe)?$` and takes the newest. The loose rule launched the clipboard tester. |
| GIMP is single-instance. | `gimp-3.2.exe <file>` hands the file to the running GIMP; `open_document` does not get a second GIMP and does not need one. |
| `Gimp.file_save` to the image's own file leaves it clean. | The `*` leaves the title after Save to PLM, as after a real Save. |
| A parasite without `PARASITE_PERSISTENT` is not in the saved file. | The fake GIMP is faithful about exactly this. |
| stderr is shown in the Error Console. | `warnings.simplefilter("ignore")` at the entry point; a Popen child must not inherit the pipes. |

## Running the tests

```bash
python -m pytest tests/ -q
```

`tests/fakegimp.py` stands up `Gimp`, `Gio`, `Image`, `Layer`, `Parasite` — only what the add-in
touches, faithful about persistence. The autouse fixture patches `host.LOG_PATH`, `state._PATH`,
`host.open_document`, `host.open_url` and `host.upload_copy`, so no test writes the user's real log
or document map. One did, and its line turned up in a live driving session.

## The server side

On the Engine: MIME row `xcf` → `image/x-xcf`; numbering `GimpImage` → `GMP-########-XCF`; type
`n5GimpImage` (cloned from a document type, twelve connector mappings); template `GIMP Image.xcf`
uploaded to the vault and attached. All through the API; `POST /api/types` hot-registers. Only
GIMP writes XCF, so the template is made by the plug-in in `tools/nexus-plm-build-template/`.

## Building the installer

```
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" installer\Nexus.PLM.Gimp.Addin.iss
```

Per user, no elevation, into the plug-ins folder of the **newest** `%APPDATA%\GIMP\<version>`
profile, chosen at install time and compared as numbers ("3.10" > "3.2"). `tests/test_installer.py`
holds the script against the source (version, plug-in name, payload, uninstall scope). One ISPP
trap: a `[Code]` line may not *begin* with `#13#10`.

## Debugging

- Add-in log: `%APPDATA%\NexusPLM\Logs\plmgimpaddin.log`.
- Document map: `%APPDATA%\NexusPLM\gimp-documents.json`.
- `curl http://localhost:5100/api/auth/me` — who the tray is signed in as.
- `curl "http://localhost:5100/plm/state?file_path=C:\Nexus\Staging\GMP-00000002-XCF.xcf"` — what PLM thinks a file is.
