#!/usr/bin/env python3
"""The Nexus PLM plug-in for GIMP: every command in its own Nexus PLM menu.

GIMP registers a plug-in by asking one :class:`Gimp.PlugIn` for the procedures it provides, so
unlike the Inkscape add-in - which needs one ``.inx`` file per menu entry - all twenty-one entries
come from the single table in :mod:`nexusplm.menu`. One place to add a command, and the menu, the
dispatch and the tests all follow from it - the table is in its own module precisely so a test can
read it without importing ``gi``.

**Two GIMP rules that are not obvious and cost time when broken:**

* The plug-in must live at ``plug-ins/<name>/<name>.py`` - the folder and the file share a name.
  Put the file anywhere else and GIMP does not see it, and says nothing about why.
* On anything but Windows the file must be executable. GIMP skips a plug-in it cannot run, again
  in silence.

**stderr is a user interface here.** GIMP collects what a plug-in writes to stderr and shows it in
the Error Console, so a stray Python warning reads as a broken add-in. Warnings are silenced for
the same reason the Inkscape add-in silences them.
"""

import os
import sys
import warnings

warnings.simplefilter("ignore")

# The package sits beside this file. GIMP does not promise to put the plug-in's own directory on
# sys.path, and a plug-in that works only because of an undocumented convenience is one that
# breaks on the next release.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gi                                                              # noqa: E402

gi.require_version("Gimp", "3.0")
from gi.repository import Gimp                                         # noqa: E402
from gi.repository import GLib                                         # noqa: E402

from nexusplm import commands                                          # noqa: E402
from nexusplm.menu import (LABELS, MENU_PATH, command_of,               # noqa: E402
                           procedures)
from nexusplm import host                                              # noqa: E402
from nexusplm.client import DEFAULT_BASE_URL, ServiceUnavailable       # noqa: E402

TRAY_IS_DOWN = (
    "Cannot reach Nexus PLM on %s\n\n"
    "Nothing can be saved to or read from PLM until the Nexus PLM tray application is running. "
    "Start it from the Start menu and run the command again." % DEFAULT_BASE_URL
)


class NexusPlm(Gimp.PlugIn):
    """Every Nexus PLM command GIMP can run."""

    def do_query_procedures(self):
        return procedures()

    def do_create_procedure(self, name):
        command = command_of(name)
        label = LABELS.get(command, command)

        procedure = Gimp.ImageProcedure.new(
            self, name, Gimp.PDBProcType.PLUGIN, self._run, None)
        procedure.set_image_types("*")
        procedure.set_menu_label(label)
        procedure.add_menu_path(MENU_PATH)
        procedure.set_documentation(
            "Nexus PLM: %s" % label,
            "Runs the Nexus PLM %s command against the open image." % label,
            name)
        procedure.set_attribution("Nexus PLM", "Nexus PLM", "2026")
        return procedure

    def _run(self, procedure, run_mode, image, drawables, config, run_data):
        command = command_of(procedure.get_name())
        try:
            commands.run(command, image)
        except ServiceUnavailable:
            host.log("%s: the tray application is not running" % command)
            # GIMP's own message, so it lands in the Error Console and the status bar rather than
            # in a toast the tray would have had to draw - and the tray is the thing that is down.
            Gimp.message(TRAY_IS_DOWN)
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


Gimp.main(NexusPlm.__gtype__, sys.argv)
