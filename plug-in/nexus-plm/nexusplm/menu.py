"""What appears in the Nexus PLM menu, and what each entry runs.

In its own module, away from the plug-in entry point, for one reason: the entry point imports
``gi`` and so can only be loaded inside GIMP. The menu is a plain table with no GIMP in it, and
keeping it here is what lets a test check that every entry has a command and every command has an
entry - the two lists that drift.
"""

#: Where every entry appears: a menu of its own on GIMP's menu bar, beside File and Edit.
#:
#: NOT under Filters, which is where a plug-in goes by default and where this started. Marc asked
#: why it was there and the honest answer was "because that is where plug-ins land". Nexus PLM is
#: not a filter - nothing here transforms pixels - it is document management, and LibreOffice and
#: OpenOffice both give it a menu of its own. GIMP will create a top-level menu for a path that
#: names one, so it gets the same treatment.
MENU_PATH = "<Image>/Nexus PLM/"

#: Procedure names are GIMP-wide, so they carry the product as a prefix.
PROCEDURE_PREFIX = "nexus-plm-"

#: Every menu entry: the command :mod:`nexusplm.commands` dispatches on, and its label.
#:
#: GIMP sorts a menu's entries alphabetically itself - measured, not assumed - so the grouping
#: below is documentation rather than presentation. It is grouped the way the other Nexus add-ins
#: group their toolbars so a reader can see the command set is the same one.
MENU = [
    # Account
    ("sign-in",           "Sign In..."),
    ("sign-out",          "Sign Out"),
    # Data management
    ("new-from-template", "New from Template..."),
    ("open-from-plm",     "Open from PLM..."),
    ("search",            "Search..."),
    ("save-to-plm",       "Save to PLM"),
    ("save-as-new",       "Save As New Item..."),
    ("save-as-existing",  "Save As Existing Item..."),
    # Lifecycle
    ("check-out",         "Check Out"),
    ("check-in",          "Check In"),
    ("revise",            "Revise"),
    ("change-owner",      "Change Ownership..."),
    # Workflow
    ("worklist",          "My Worklist..."),
    ("new-workflow",      "New Workflow..."),
    # Attributes
    ("properties",        "Properties..."),
    ("edit-values",       "Edit Values..."),
    ("refresh-values",    "Refresh Values"),
    # Information
    ("settings",          "Current Settings..."),
    ("connection-status", "Connection Status"),
    ("help",              "Help"),
    ("about",             "About"),
]

#: The label for each command, for the procedure's menu entry and documentation.
LABELS = dict(MENU)


def procedure_name(command):
    """``check-out`` becomes ``nexus-plm-check-out``."""
    return PROCEDURE_PREFIX + command


def command_of(name):
    """The command a procedure name stands for, or ``None`` if it is not one of ours."""
    if not name.startswith(PROCEDURE_PREFIX):
        return None
    return name[len(PROCEDURE_PREFIX):]


def procedures():
    """Every procedure name this plug-in provides, in menu order."""
    return [procedure_name(command) for command, _label in MENU]
