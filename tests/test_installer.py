"""The installer script, held against the source it ships.

An Inno script is text nobody runs until release day, and every value in it that also lives
somewhere else - the version, the plug-in's name, the files - is a value that drifts. These tests
read the .iss as text and check each against where it really comes from, so a drift fails here
rather than on a user's machine.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "plug-in", "nexus-plm"))
sys.path.insert(0, os.path.join(ROOT, "plug-in"))

import build  # noqa: E402
from nexusplm import commands  # noqa: E402

ISS = os.path.join(ROOT, "installer", "Nexus.PLM.Gimp.Addin.iss")


def script():
    with open(ISS, encoding="utf-8") as handle:
        return handle.read()


def define(name):
    match = re.search(r'^#define %s\s+"([^"]*)"' % re.escape(name), script(), re.MULTILINE)
    assert match, "no #define %s in the installer" % name
    return match.group(1)


class TestTheVersion:
    def test_the_installer_ships_the_version_the_add_in_reports(self):
        assert define("AppVersion") == commands.VERSION


class TestThePluginName:
    """GIMP only runs plug-ins\\<name>\\<name>.py. Every place that name appears must agree."""

    def test_it_is_the_folder_build_py_installs(self):
        assert define("PluginName") == build.PLUGIN

    def test_the_folder_and_the_entry_point_share_it(self):
        name = define("PluginName")
        folder = os.path.join(ROOT, "plug-in", name)
        assert os.path.isdir(folder), "no plug-in folder " + name
        assert os.path.isfile(os.path.join(folder, name + ".py")), \
            "GIMP needs %s\\%s.py - folder and file sharing a name" % (name, name)


class TestThePayload:
    def test_the_source_folder_exists_and_holds_the_package(self):
        name = define("PluginName")
        assert os.path.isdir(os.path.join(ROOT, "plug-in", name, "nexusplm"))

    def test_the_destination_is_a_plug_ins_folder_under_a_gimp_profile(self):
        """Chosen at install time, but it must end where GIMP looks."""
        body = script()
        assert r"{code:GimpPluginsDir}\{#PluginName}" in body
        assert "\\plug-ins'" in body   # GimpPluginsDir appends \plug-ins

    def test_the_developer_script_is_not_shipped(self):
        """plug-in\\build.py sits beside the plug-in folder and must not go with it."""
        sources = re.findall(r'^Source:\s*"([^"]+)"', script(), re.MULTILINE)
        assert sources
        assert all("build.py" not in s for s in sources)
        # The only source is the plug-in folder itself - written with the macro, so it is the
        # macro's name that must appear, not the folder's. Checking for the folder's name here
        # was the first version of this test, and it failed against a correct installer.
        assert all("{#PluginName}" in s for s in sources)

    def test_compiled_python_is_excluded(self):
        assert "__pycache__" in script()


class TestVersionFolderChoice:
    """The newest GIMP profile wins, compared as a version and not as text."""

    def test_versions_are_compared_numerically_not_as_strings(self):
        # "3.10" is newer than "3.2"; as text it would sort earlier. The script says so in words
        # and implements it with StrToIntDef - both must be present.
        body = script()
        assert "StrToIntDef" in body
        assert '"3.10" sorts before "3.2" as text' in body

    def test_no_profile_falls_back_to_the_version_it_was_written_for(self):
        assert "Best := '3.2'" in script()


class TestUninstall:
    def test_it_removes_only_the_plug_in_folder(self):
        body = script()
        assert r'{code:GimpPluginsDir}\{#PluginName}' in body
        assert not re.search(r'Name:\s*"\{code:GimpPluginsDir\}"\s*$', body, re.MULTILINE)
