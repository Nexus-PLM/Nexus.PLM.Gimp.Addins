"""The command bodies, driven with a fake service and a fake GIMP."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "plug-in", "nexus-plm"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

import fakegimp  # noqa: E402
from fakegimp import Gimp, Gio, Image, Layer  # noqa: E402

from nexusplm import commands, host, menu, state, xcf  # noqa: E402
from nexusplm.client import ServiceUnavailable  # noqa: E402


class FakeClient:
    """Records what was asked of it and answers whatever the test set up."""

    def __init__(self, **answers):
        self.answers = answers
        self.calls = []
        self.said = []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append(name)
            return self.answers.get(name, {"success": True})
        return call

    def notify(self, message, severity="info"):
        self.said.append((severity, message))
        self.calls.append("notify")
        return {"success": True}


#: The genuine implementations, captured before any test patches the names. The add-in passes
#: ``gimp``/``gio`` in so they can be injected; here they are bound to the fake once, and the
#: commands then call them without knowing.
_REAL_WRITE_VALUES = xcf.write_values
_REAL_WRITE_INTO_FILE = xcf.write_into_file


@pytest.fixture(autouse=True)
def no_real_side_effects(monkeypatch, tmp_path):
    """Never write the real log, never launch GIMP, never open a browser, never reach real GIMP."""
    fakegimp.reset()
    monkeypatch.setattr(host, "LOG_PATH", str(tmp_path / "addin.log"))
    # And never the real document map. A test wrote "c:/staging/gmp-000005-xcf.xcf -> obj-5"
    # into the user's own map, where it sat looking like something the add-in had really done.
    # A test that leaves a trace in live state will mislead somebody at the worst moment.
    monkeypatch.setattr(state, "_PATH", str(tmp_path / "documents.json"))
    monkeypatch.setattr(host, "open_document", lambda path: None)
    monkeypatch.setattr(host, "open_url", lambda url: None)
    monkeypatch.setattr(
        host, "upload_copy",
        lambda image, path, gimp=None, gio=None:
        str(tmp_path / os.path.basename(path or "Untitled.xcf")))
    monkeypatch.setattr(
        xcf, "write_values",
        lambda image, values, gimp=None: _REAL_WRITE_VALUES(image, values, gimp=Gimp))
    monkeypatch.setattr(
        xcf, "write_into_file",
        lambda path, values, gimp=None, gio=None:
        _REAL_WRITE_INTO_FILE(path, values, gimp=Gimp, gio=Gio))


def context(client=None, image=None, path="C:/images/GMP-000001-XCF.xcf"):
    return commands.Context(client or FakeClient(), image or Image(path=path), path)


class TestTheMenuAndTheCommandsAgree:
    """A menu entry with no command is a dead entry; a command with no entry is unreachable."""

    def test_every_menu_entry_has_a_command(self):
        assert [c for c, _ in menu.MENU if c not in commands.COMMANDS] == []

    def test_every_command_is_on_the_menu(self):
        on_menu = {c for c, _ in menu.MENU}
        assert sorted(set(commands.COMMANDS) - on_menu) == []

    def test_procedure_names_are_distinct(self):
        names = menu.procedures()
        assert len(names) == len(set(names))

    def test_a_procedure_name_round_trips_to_its_command(self):
        for command, _label in menu.MENU:
            assert menu.command_of(menu.procedure_name(command)) == command

    def test_a_foreign_procedure_name_is_not_ours(self):
        assert menu.command_of("gimp-blur") is None


class TestAnUnregisteredImage:
    def test_it_is_told_so_rather_than_failing(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: None)
        client = FakeClient()
        commands.check_out(context(client))
        assert any("not registered in PLM" in m for _s, m in client.said)
        assert "check_out" not in client.calls


class TestAnUnsavedImage:
    def test_save_as_new_says_to_save_first(self):
        client = FakeClient()
        commands.save_as_new(context(client, image=Image(), path=None))
        assert any("never been saved" in m for _s, m in client.said)
        assert "save_as_new" not in client.calls


class TestWhatGetsUploaded:
    def test_save_to_plm_sends_a_written_copy_not_the_users_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient()
        sent = {}
        monkeypatch.setattr(client, "save",
                            lambda item_id, path: sent.update(path=path) or {"success": True})
        ctx = context(client)
        commands.save_to_plm(ctx)
        assert sent["path"] != ctx.path
        assert os.path.basename(sent["path"]) == "GMP-000001-XCF.xcf"

    def test_check_in_sends_one_too(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient()
        commands.check_in(context(client))
        assert "check_in" in client.calls


class TestValuesReachTheImage:
    def test_refresh_writes_the_record(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(refresh_values={
            "success": True,
            "attribute_mappings": {"PartNumber": "GMP-000001-XCF", "Revision": "B"},
        })
        ctx = context(client)
        commands.refresh_values(ctx)
        assert xcf.read_values(ctx.image) == {"PartNumber": "GMP-000001-XCF", "Revision": "B"}

    def test_edit_values_writes_only_when_the_dialog_was_saved(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(edit_values={
            "success": True, "saved": False, "attribute_mappings": {"Revision": "Z"}})
        ctx = context(client)
        commands.edit_values(ctx)
        assert xcf.read_values(ctx.image) == {}

    def test_an_item_with_no_mapped_attributes_says_so(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(refresh_values={"success": True, "attribute_mappings": {}})
        commands.refresh_values(context(client))
        assert any("Nothing to update" in m for _s, m in client.said)


class TestTheStagedFile:
    def test_new_from_template_writes_the_record_before_opening(self, monkeypatch):
        """Otherwise the image arrives carrying nothing, on an item PLM has just numbered."""
        path = "C:/staging/GMP-000005-XCF.xcf"
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, Image(path=path),
                       Gio.File.new_for_path(path), None)

        opened = []
        monkeypatch.setattr(host, "open_document", lambda p: opened.append(p))
        client = FakeClient(new={
            "success": True, "file_path": path, "plm_object_id": "obj-5",
            "part_number": "GMP-000005-XCF",
            "attribute_mappings": {"PartNumber": "GMP-000005-XCF", "Revision": "A"},
        })
        commands.new_from_template(context(client))

        assert opened == [path]
        again = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(path))
        assert xcf.read_values(again) == {"PartNumber": "GMP-000005-XCF", "Revision": "A"}

    def test_an_item_with_no_staged_file_is_reported(self):
        client = FakeClient(new={"success": True})
        ctx = context(client)
        commands.new_from_template(ctx)
        assert any("did not stage a file" in m for _s, m in client.said)


class TestRefusalsAreShown:
    def test_the_services_own_reason_is_what_the_user_reads(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(check_out={"success": False, "error": "Already checked out to jdoe."})
        commands.check_out(context(client))
        assert any("Already checked out to jdoe." in m for _s, m in client.said)

    def test_a_cancelled_dialog_says_nothing(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(properties={"success": False, "cancelled": True})
        commands.properties(context(client))
        assert client.said == []


class TestRun:
    def test_an_unexpected_failure_becomes_a_sentence_not_a_traceback(self, monkeypatch):
        monkeypatch.setitem(commands.COMMANDS, "explode",
                            lambda ctx: (_ for _ in ()).throw(ValueError("kaboom")))
        said = []
        monkeypatch.setattr(host, "say", lambda client, msg, severity="info": said.append(msg))
        commands.run("explode", Image(path="C:/images/x.xcf"))
        assert any("kaboom" in m for m in said)

    def test_an_unreachable_service_is_raised_for_the_entry_point(self, monkeypatch):
        def unreachable(ctx):
            raise ServiceUnavailable("no tray")
        monkeypatch.setitem(commands.COMMANDS, "unreachable", unreachable)
        with pytest.raises(ServiceUnavailable):
            commands.run("unreachable", Image(path="C:/images/x.xcf"))

    def test_an_unknown_command_does_nothing_quietly(self):
        commands.run("no-such-command", Image(path="C:/images/x.xcf"))
