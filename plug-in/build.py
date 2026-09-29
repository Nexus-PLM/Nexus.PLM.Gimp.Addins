#!/usr/bin/env python3
"""Install the Nexus PLM plug-in into GIMP.

    python build.py --install          # copy into the user's GIMP plug-ins directory
    python build.py --install --gimp 3.2

There is nothing to generate - unlike Inkscape, GIMP takes its whole menu from the plug-in's own
``do_query_procedures``, so the menu lives in ``nexus-plm.py`` and this script only copies.

**GIMP's two silent rules**, both of which this script exists to get right:

* the plug-in must be at ``plug-ins/<name>/<name>.py``, folder and file sharing a name;
* on anything but Windows the file must be executable.

Break either and GIMP simply does not show the plug-in, with nothing in the log to say why.
"""

import argparse
import os
import shutil
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

#: The plug-in folder, whose name must match the ``.py`` inside it.
PLUGIN = "nexus-plm"

#: GIMP versions to install into when none is named, newest first.
KNOWN_VERSIONS = ["3.2", "3.0"]


def user_plugin_dirs(version=None):
    """Every GIMP user plug-ins directory to install into, per platform."""
    versions = [version] if version else KNOWN_VERSIONS

    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        roots = [os.path.join(base, "GIMP", v) for v in versions]
    elif sys.platform == "darwin":
        roots = [os.path.expanduser("~/Library/Application Support/GIMP/%s" % v) for v in versions]
    else:
        roots = [os.path.expanduser("~/.config/GIMP/%s" % v) for v in versions]

    # Only those that exist: creating a directory for a GIMP that is not installed leaves litter
    # and tells the user nothing.
    return [os.path.join(r, "plug-ins") for r in roots if os.path.isdir(r)]


def install(target):
    """Copy the plug-in folder into ``target``, replacing any previous copy."""
    os.makedirs(target, exist_ok=True)
    destination = os.path.join(target, PLUGIN)

    # Replace rather than merge: a module deleted from the source must not survive in the
    # installed copy, which is how a stale file goes on being imported for weeks.
    shutil.rmtree(destination, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, PLUGIN), destination,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    entry = os.path.join(destination, PLUGIN + ".py")
    if sys.platform != "win32":
        mode = os.stat(entry).st_mode
        os.chmod(entry, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true",
                        help="copy the plug-in into GIMP's user plug-ins directory")
    parser.add_argument("--gimp", help="a specific GIMP version, e.g. 3.2")
    parser.add_argument("--target", help="install somewhere other than the default")
    arguments = parser.parse_args()

    if not arguments.install:
        print("nothing to build - the menu lives in %s.py. Pass --install to deploy." % PLUGIN)
        return

    targets = [arguments.target] if arguments.target else user_plugin_dirs(arguments.gimp)
    if not targets:
        raise SystemExit("No GIMP user directory found. Is GIMP installed for this user?")

    for target in targets:
        print("installed to %s" % install(target))


if __name__ == "__main__":
    main()
