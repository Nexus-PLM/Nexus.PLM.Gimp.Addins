# Nexus PLM for GIMP

Product lifecycle management from inside GIMP. A Python plug-in that puts the same command set the
Nexus PLM add-ins give Word, LibreOffice, OpenOffice, ONLYOFFICE and Inkscape into a **Nexus PLM**
menu of its own on GIMP's menu bar.

Twenty-one commands: sign in and out, create from a template, open and search the vault, save,
save as a new or an existing item, check out and in, revise, change ownership, worklist and
workflow, properties, edit and refresh attribute values, settings, connection status, help and
about.

Tested against GIMP **3.2.6** (bundled Python 3.14).

---

## The attributes are in the file

That is the whole point of this add-in. Every attribute PLM maps for the item is written into the
image's own **parasite** - GIMP's mechanism for arbitrary named data attached to an image - so a
`.xcf` carries its part number, revision and the rest wherever it goes. No sidecar, no database
row keyed on a filename.

Measured on 3.2.6 before a line of this was written: attach a parasite with
`PARASITE_PERSISTENT`, save, reload, and the value comes back byte for byte. **The flag is the
whole trick** - without it a parasite lives only as long as the image is open and is silently
absent from the saved file.

Read it out of a staged file with nothing but Python:

```
{ "PartNumber": "GMP-00000002-XCF", "Revision": "A",
  "Description": "GIMP image opened by the add-in",
  "CreatedBy": "admin", "CreationDate": "2026-09-29T03:09:40Z", ... }
```

An image can *also* show a value, by having a text layer named after the attribute key - the
add-in fills those in. Most will not, and nothing depends on it.

**What a parasite does not do is survive export.** A PNG or JPEG exported from the image carries
none of it. If exported images ever need to stay identifiable, XMP metadata is the place, and
GIMP exposes it - deliberately not done, because nobody has asked and an unused second record is
a second thing to keep in step.

## How it fits together

The plug-in talks to **one** thing: the Nexus PLM Addin Service on `http://localhost:5100`,
carried by the Nexus PLM tray application. It never reaches the Engine or the vault itself.

```
GIMP  ──►  nexus-plm.py  ──►  nexusplm/commands.py  ──►  Addin Service (localhost:5100)
                                     │                          │
                                nexusplm/xcf.py          the tray's dialogs and toasts
                                (the parasite record)
```

`client.py`, `state.py`, `identity.py` and `navigator.py` are shared with the LibreOffice and
Inkscape add-ins and carry no GIMP API at all.

## Building and installing

```bash
python plug-in/build.py --install     # copy into GIMP's user plug-ins directory
python -m pytest tests/ -q
```

**GIMP's two silent rules**, which `build.py` exists to get right: the plug-in must live at
`plug-ins/<name>/<name>.py` with the folder and file sharing a name, and on anything but Windows
the file must be executable. Break either and GIMP simply does not show it, with nothing in the
log to say why.

## The server side

| | |
|---|---|
| Type | `n5GimpImage` ("GIMP Image"), cloned from `n5LibreOfficeTrackingDoc` |
| Numbering | `GimpImage` → `GMP-00000001-XCF` |
| MIME | `image/x-xcf` |
| Template | `GIMP Image.xcf`, built by `tools/nexus-plm-build-template` |

## Tests

48, and they need no GIMP: `tests/fakegimp.py` stands up the pieces the add-in actually touches,
and is faithful about the one that matters - a parasite is only persisted when it carries the
persistent flag.

## Licence

MIT. See [LICENSE](LICENSE).
