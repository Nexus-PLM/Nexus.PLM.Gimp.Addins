"""The GIMP-shaped helpers, tested without GIMP."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "plug-in", "nexus-plm"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

from fakegimp import Image  # noqa: E402
from nexusplm import host  # noqa: E402


@pytest.fixture(autouse=True)
def never_the_real_log(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "LOG_PATH", str(tmp_path / "logs" / "addin.log"))


class TestDocumentPath:
    def test_a_saved_image_answers_its_file(self):
        assert host.document_path(Image(path=r"C:\images\GMP-1.xcf")) == r"C:\images\GMP-1.xcf"

    def test_an_image_never_saved_is_none(self):
        assert host.document_path(Image()) is None


class TestFindingGimp:
    """The heuristic that picked a debug tool, and the rule that replaced it.

    A GIMP bin directory really contains all of these. The first version of gimp_executable took
    everything starting with "gimp-", sorted, and used the last - gimp-test-clipboard.exe. Open
    from PLM launched it, no window appeared, and the command reported success.
    """

    REAL_BIN = [
        "gimp-3.2.exe", "gimp-3.exe", "gimp-console-3.2.exe",
        "gimp-debug-tool-3.2.exe", "gimp-debug-tool-3.exe", "gimp-debug-tool.exe",
        "gimp-script-fu-interpreter-3.0.exe",
        "gimp-test-clipboard-3.2.exe", "gimp-test-clipboard-3.exe", "gimp-test-clipboard.exe",
        "python.exe", "pythonw.exe",
    ]

    def _bin(self, tmp_path, names):
        folder = tmp_path / "bin"
        folder.mkdir()
        for name in names:
            (folder / name).write_bytes(b"")
        return folder

    def _found(self, tmp_path, monkeypatch, names):
        folder = self._bin(tmp_path, names)
        monkeypatch.setattr(host.sys, "executable", str(folder / "python.exe"))
        found = host.gimp_executable()
        return os.path.basename(found) if found else None

    def test_it_picks_gimp_itself_not_a_debug_tool(self, tmp_path, monkeypatch):
        assert self._found(tmp_path, monkeypatch, self.REAL_BIN) == "gimp-3.2.exe"

    def test_it_never_picks_the_clipboard_tester(self, tmp_path, monkeypatch):
        assert "test-clipboard" not in self._found(tmp_path, monkeypatch, self.REAL_BIN)

    def test_it_never_picks_the_console_build(self, tmp_path, monkeypatch):
        """gimp-console has no window, so opening a file with it shows the user nothing."""
        assert "console" not in self._found(tmp_path, monkeypatch, self.REAL_BIN)

    def test_the_newest_version_wins(self, tmp_path, monkeypatch):
        assert self._found(tmp_path, monkeypatch,
                           ["gimp-3.exe", "gimp-3.2.exe", "gimp-3.10.exe", "python.exe"]) \
            == "gimp-3.10.exe"

    def test_an_unversioned_gimp_is_accepted(self, tmp_path, monkeypatch):
        assert self._found(tmp_path, monkeypatch, ["gimp.exe", "python.exe"]) == "gimp.exe"

    def test_nothing_found_answers_none(self, tmp_path, monkeypatch):
        assert self._found(tmp_path, monkeypatch,
                           ["gimp-debug-tool.exe", "python.exe"]) is None


class TestLogging:
    def test_a_line_is_written(self, tmp_path, monkeypatch):
        monkeypatch.setattr(host, "LOG_PATH", str(tmp_path / "logs" / "addin.log"))
        host.log("check-out: started")
        assert "check-out: started" in open(host.LOG_PATH, encoding="utf-8").read()

    def test_a_log_that_cannot_be_written_does_not_fail_the_command(self, monkeypatch):
        monkeypatch.setattr(host, "LOG_PATH", "\x00:/nowhere/addin.log")
        host.log("this must not raise")
