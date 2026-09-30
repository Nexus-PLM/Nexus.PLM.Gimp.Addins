"""Where a PLM value lives inside a GIMP image, and how it is read back.

**The record is the point.** Every mapped attribute goes into a single image **parasite** - GIMP's
own mechanism for arbitrary named data attached to an image - so the attributes travel inside the
``.xcf`` itself rather than in a sidecar file or a database row keyed on a filename. Measured on
GIMP 3.2.6: attach a parasite with ``PARASITE_PERSISTENT``, save, reload, and the value comes back
byte for byte.

    parasite_survives_xcf: true
    parasite_value: {"PartNumber": "IMG-000001-XCF", "Revision": "A"}

The flag is the whole trick. Without ``PARASITE_PERSISTENT`` a parasite lives only as long as the
image is open and is silently absent from the saved file - which would look exactly like this
module not working.

A second, optional half writes values into **text layers named after the attribute key**, the same
convenience the Inkscape add-in offers through ``inkscape:label``. Most images will not have them,
and nothing depends on it: an image with no such layer still carries every value in its parasite.

**What a parasite does not do is survive export.** It is an XCF feature, so a PNG or JPEG exported
from the image carries none of it. If exported images ever need to stay identifiable, the place
for that is XMP metadata, which GIMP exposes through ``Gimp.Image.get_metadata`` - deliberately
not done here, because nobody has asked for it and an unused second record is a second thing to
keep in step.
"""

import json

#: The parasite's name. Slash-separated like GIMP's own (``gimp-comment``, ``exif-data``), and
#: namespaced so it cannot collide with a plug-in someone else wrote.
PARASITE = "nexus-plm/attributes"

#: GIMP's flag for "write this into the file". Looked up rather than hardcoded so the module can
#: be imported and tested without GIMP present - the value is 1, but the name is the contract.
PERSISTENT_FLAG = 1


def read_values(image):
    """Every PLM value recorded in the image, as ``{key: text}``.

    An image that has never been in PLM has no parasite, which is not an error and answers an
    empty dict. So does a parasite whose contents cannot be read - a half-written record is worth
    no more than an absent one, and refusing to open the image over it would help nobody.
    """
    parasite = image.get_parasite(PARASITE)
    if parasite is None:
        return {}
    try:
        payload = bytes(parasite.get_data())
        values = json.loads(payload.decode("utf-8"))
    except Exception:
        return {}
    return values if isinstance(values, dict) else {}


#: Keys PLM stamps itself. An image's copies of them are never offered back as the values of a
#: new item. Save As New merges whatever a caller offers straight onto the new revision (only
#: ``plm_`` keys are refused), so an image copied from another item would hand the new item its
#: old part number, and a template's empty record wiped ``createdBy`` and ``creationDate`` to ""
#: - measured on the Inkscape add-in, IND-00000007-SVG, 29 Sep 2026: every value came back blank.
SYSTEM_KEYS = frozenset(k.lower() for k in (
    "PartNumber", "Revision", "CreatedBy", "CreationDate", "ModifiedBy", "ModificationDate"))


def offerable_values(image):
    """The image's values a new item may take as defaults: filled in, and not PLM's own.

    An empty entry in the record is a slot the template left for PLM to fill, not a value of "";
    offering it as "" is how the blanks above were written. And the identity and stamp keys belong
    to the server whatever the image says.
    """
    return {key: value for key, value in read_values(image).items()
            if value and key.lower() not in SYSTEM_KEYS}


def write_values(image, values, gimp=None):
    """Record ``values`` in the image's parasite and draw any the image is set up to show.

    Returns ``(recorded, drawn)`` - how many values were written to the record and how many text
    layers were changed. The two differ on purpose and the caller says both: "wrote 7 value(s),
    2 shown" stops someone hunting for a value the image was never asked to display.

    ``gimp`` is the ``Gimp`` module, passed in rather than imported so this can be tested without
    GIMP. Callers inside a plug-in pass the real one.
    """
    if not values:
        return 0, 0

    merged = read_values(image)
    for key, value in values.items():
        merged[key] = "" if value is None else str(value)

    payload = json.dumps(merged, indent=2, sort_keys=True).encode("utf-8")

    if gimp is None:
        from gi.repository import Gimp as gimp                     # noqa: N813

    parasite = gimp.Parasite.new(PARASITE, PERSISTENT_FLAG, payload)
    image.attach_parasite(parasite)

    return len(values), draw_values(image, values)


def draw_values(image, values):
    """Put each value into the text layer named after its key, where one exists.

    Returns how many were drawn. A key with no matching layer is skipped in silence: an image is
    not obliged to show any of its item's attributes, and most show none.
    """
    drawn = 0
    for layer in _text_layers(image):
        key = layer.get_name()
        if key not in values:
            continue
        try:
            layer.set_text(for_display(values[key]))
            drawn += 1
        except Exception:
            # A layer that will not take text is not worth failing a command over - the record,
            # which is the part that matters, is already written.
            continue
    return drawn


def _text_layers(image):
    """Every text layer in the image, including those inside groups.

    A plain ``get_layers`` answers only the top level, so a title block tucked into a group would
    be invisible to this - which is exactly where someone would put it.
    """
    found = []

    def walk(layers):
        for layer in layers:
            try:
                if layer.is_group():
                    walk(layer.get_children())
                    continue
            except Exception:
                pass
            if _is_text(layer):
                found.append(layer)

    walk(image.get_layers())
    return found


def _is_text(layer):
    try:
        return bool(layer.is_text_layer())
    except Exception:
        return False


def labelled_keys(image):
    """Every key the image is prepared to show, from the names of its text layers."""
    keys = []
    for layer in _text_layers(image):
        name = layer.get_name()
        if name and name not in keys:
            keys.append(name)
    return keys


def write_into_file(path, values, gimp=None, gio=None):
    """Put ``values`` into an ``.xcf`` **file**, for an image GIMP has not opened yet.

    New from Template opens the staged file in a **new** GIMP, so there is no live image to write
    the record into. Without this the drawing arrives carrying nothing, on an item PLM has just
    numbered - which is exactly what the Inkscape add-in had to be fixed for.

    Loads the file, writes the parasite, saves it back and closes it. Returns ``(recorded,
    drawn)`` as :func:`write_values` does.
    """
    if not path or not values:
        return 0, 0

    if gimp is None:
        from gi.repository import Gimp as gimp                      # noqa: N813
    if gio is None:
        from gi.repository import Gio as gio                        # noqa: N813

    handle = gio.File.new_for_path(path)
    image = gimp.file_load(gimp.RunMode.NONINTERACTIVE, handle)
    try:
        recorded, drawn = write_values(image, values, gimp=gimp)
        gimp.file_save(gimp.RunMode.NONINTERACTIVE, image, handle, None)
    finally:
        try:
            image.delete()
        except Exception:
            pass
    return recorded, drawn


def for_display(value):
    """How a value reads on the canvas, as opposed to how it is recorded.

    The record keeps exactly what the service sent, because Refresh Values compares against it.
    A person reading a title block wants a date, not ``2026-09-28T02:24:15.3456789Z``. Only that
    one case is handled - guessing at formats is how a part number loses a character.
    """
    if value is None:
        return ""
    text = str(value)
    if len(text) >= 11 and text[10] == "T" and text[4] == "-" and text[7] == "-":
        head = text[:10]
        if head.replace("-", "").isdigit():
            return head
    return text
