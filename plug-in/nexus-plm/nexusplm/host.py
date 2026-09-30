"""The parts that know they are inside GIMP.

Everything GIMP-shaped lives here so the command bodies do not have to care: where the log goes,
what the open image's file is, how to put a file in front of the user, and how to say something
to them.

**GIMP differs from Inkscape in the one way that matters.** An Inkscape extension is handed a copy
of the document and cannot save it; a GIMP plug-in holds the live ``Gimp.Image`` and *can* write
it out. So this add-in behaves like the office ones: it writes the current image to a file and
uploads that, with no guessing about whether the disk is up to date.

It writes a **temp copy** rather than the user's own file, for two reasons. Saving over their file
is a side effect nobody asked a PLM command to have - Save to PLM should not silently flatten an
imported PNG into an XCF at its original path. And the copy can be named by the document's own
file name, which is what the vault names the dataset from.
"""

import os
import re
import subprocess
import sys

#: Beside every other Nexus add-in's log, under its own name so two hosts never share a file.
LOG_PATH = os.path.join(
    os.environ.get("APPDATA") or os.path.expanduser("~"),
    "NexusPLM", "Logs", "plmgimpaddin.log")

HELP_URL = "https://github.com/Nexus-PLM/Nexus.PLM.Gimp.Addins"


def log(message):
    """A line in the shared log. Best effort - a command must not fail over a log write."""
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except Exception:
        pass


def document_path(image):
    """The file the open image came from, or ``None`` when it has never been saved.

    ``None`` is a normal state, not a failure: an image scanned or pasted into GIMP has no file
    yet, and Save As New Item is exactly the command for it.
    """
    try:
        gio_file = image.get_file()
    except Exception:
        return None
    if gio_file is None:
        return None
    try:
        return gio_file.get_path() or None
    except Exception:
        return None


def upload_copy(image, path, gimp=None, gio=None):
    """Write the image as it stands, as XCF, to its own file, and answer that path for PLM.

    Two decisions here, both paid for.

    **XCF and not the original format**: the parasite carrying the PLM record is an XCF feature,
    so a PNG would reach the vault with the picture and none of the attributes. The type this
    add-in registers against is an XCF type for the same reason. An image whose file is not
    ``.xcf`` is written to a sibling ``.xcf`` of the same name, and that is what PLM takes.

    **The image's own file, not a copy under %TEMP%.** The first version wrote a temp copy so no
    PLM command would save over the user's file. But ``SaveRequest`` has one ``FilePath``, which the
    service both reads and **records as the item's ``plm_file_path``** - so the temp copy became
    the item's home, and Revise staged the next revision under %TEMP% and opened it in a second
    window (measured on the Inkscape add-in, which shares this design). Marc: "it must get written
    to the staging directory." For an item PLM handed over, the image's own file IS the staged file.

    ``path`` is required: an image that has never been saved has no file for PLM to take, and the
    commands refuse that case before reaching here.
    """
    if not path:
        raise ValueError("an image with no file cannot be uploaded")

    if gimp is None:
        from gi.repository import Gimp as gimp                      # noqa: N813
    if gio is None:
        from gi.repository import Gio as gio                        # noqa: N813

    folder, name = os.path.split(os.path.abspath(path))
    stem, extension = os.path.splitext(name)
    target = path if extension.lower() == ".xcf" else os.path.join(folder, stem + ".xcf")
    os.makedirs(folder, exist_ok=True)

    gimp.file_save(gimp.RunMode.NONINTERACTIVE, image, gio.File.new_for_path(target), None)
    return target


def same_file(a, b):
    """Whether two paths name the same file, as Windows sees it: case-insensitive, normalised."""
    if not a or not b:
        return False
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def open_document(path):
    """Show a file to the user in GIMP.

    GIMP is started on the file. Measured on 3.2: GIMP is single-instance, so the new process hands
    the file to the running GIMP and exits, and the image opens there as another window - which is
    the behaviour wanted anyway, since opening an item from the vault must not disturb whatever the
    user already had open.

    All three streams go to DEVNULL and the child is detached. GIMP, like Inkscape, reads a
    plug-in's pipes; a child holding them open is how the parent ends up waiting on a window the
    user has not closed yet.
    """
    executable = gimp_executable()
    if not executable:
        raise RuntimeError("Could not find the GIMP executable to open %s with." % path)

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0) \
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    subprocess.Popen(
        [executable, path],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True, creationflags=creation_flags,
    )


#: What GIMP's own executable is called: ``gimp``, or ``gimp`` and a version - ``gimp-3.2``,
#: ``gimp-3``. Anchored, because the loose version of this rule picked the wrong program.
_GIMP_EXECUTABLE = re.compile(r"^gimp(-\d+(\.\d+)*)?(\.exe)?$", re.IGNORECASE)


def gimp_executable():
    """Where GIMP itself is, found rather than configured.

    A plug-in runs under GIMP's own bundled Python, so the interpreter sits inside the
    installation and the executable is its sibling. The directory is scanned rather than a
    version hardcoded, because a hardcoded one breaks on the first machine that upgraded.

    **Scanned against an anchored pattern, and that is the point.** The first version took every
    name starting with ``gimp-``, sorted them, and used the last - which on this machine is

        gimp-3.2.exe, gimp-3.exe, gimp-debug-tool-3.2.exe, gimp-debug-tool-3.exe,
        gimp-debug-tool.exe, gimp-script-fu-interpreter-3.0.exe, gimp-test-clipboard-3.2.exe,
        gimp-test-clipboard-3.exe, gimp-test-clipboard.exe

    so Open from PLM cheerfully launched **gimp-test-clipboard.exe** and nothing appeared. The
    command reported success, the file was staged, and no window opened - the worst shape of
    failure. Only a name that is GIMP itself, optionally versioned, counts now, and the newest
    version wins.
    """
    here = os.path.dirname(os.path.abspath(sys.executable))
    for folder in (here, os.path.join(os.path.dirname(here), "bin")):
        if not os.path.isdir(folder):
            continue
        found = [name for name in os.listdir(folder) if _GIMP_EXECUTABLE.match(name)]
        if found:
            # Newest version last: gimp-3 before gimp-3.2, and a bare "gimp" before either.
            found.sort(key=_version_key)
            return os.path.join(folder, found[-1])
    return None


def _version_key(name):
    """Sort key putting the highest version last, and an unversioned ``gimp`` first."""
    match = _GIMP_EXECUTABLE.match(name)
    suffix = (match.group(1) or "").lstrip("-") if match else ""
    if not suffix:
        return (0,)
    return (1,) + tuple(int(part) for part in suffix.split("."))


def open_url(url):
    """Open a page in the user's browser."""
    import webbrowser
    webbrowser.open(url)


def say(client, message, severity="info"):
    """Tell the user something, through the one toast the tray host owns.

    Not GIMP's own message bar: every Nexus add-in says things in the same place, and the tray is
    the one thing that is running whichever host the user is in.
    """
    try:
        client.notify(message, severity)
    except Exception:
        log("could not post a notification: " + message)
