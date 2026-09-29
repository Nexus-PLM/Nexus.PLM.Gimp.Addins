"""Where a PLM value lives in a GIMP image, tested without GIMP."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "plug-in", "nexus-plm"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

import fakegimp  # noqa: E402
from fakegimp import Gimp, Gio, Image, Layer, parasite_json  # noqa: E402

from nexusplm import xcf  # noqa: E402


@pytest.fixture(autouse=True)
def clean():
    fakegimp.reset()


def image_with_text_layers(*names):
    return Image(layers=[Layer(name, text="-") for name in names])


class TestTheRecord:
    def test_an_image_never_in_plm_has_no_values(self):
        assert xcf.read_values(Image()) == {}

    def test_what_was_written_reads_back(self):
        image = Image()
        xcf.write_values(image, {"PartNumber": "GMP-000001-XCF", "Revision": "A"}, gimp=Gimp)
        assert xcf.read_values(image) == {"PartNumber": "GMP-000001-XCF", "Revision": "A"}

    def test_a_second_write_merges_rather_than_replaces(self):
        """Refresh Values sends what changed, not the whole set."""
        image = Image()
        xcf.write_values(image, {"PartNumber": "GMP-1"}, gimp=Gimp)
        xcf.write_values(image, {"Revision": "B"}, gimp=Gimp)
        assert xcf.read_values(image) == {"PartNumber": "GMP-1", "Revision": "B"}

    def test_a_value_is_updated_not_duplicated(self):
        image = Image()
        xcf.write_values(image, {"Revision": "A"}, gimp=Gimp)
        xcf.write_values(image, {"Revision": "B"}, gimp=Gimp)
        assert xcf.read_values(image) == {"Revision": "B"}

    def test_nothing_to_write_attaches_nothing(self):
        image = Image()
        assert xcf.write_values(image, {}, gimp=Gimp) == (0, 0)
        assert image.get_parasite(xcf.PARASITE) is None

    def test_a_none_value_is_recorded_as_empty(self):
        image = Image()
        xcf.write_values(image, {"Description": None}, gimp=Gimp)
        assert xcf.read_values(image) == {"Description": ""}

    def test_an_unreadable_parasite_reads_as_nothing(self):
        """Half a record is worth no more than none, and must not stop the image opening."""
        image = Image()
        image.attach_parasite(Gimp.Parasite.new(xcf.PARASITE, 1, b"{not json"))
        assert xcf.read_values(image) == {}


class TestItSurvivesTheFile:
    """The measured fact the whole design rests on: a persistent parasite is in the XCF."""

    def test_the_record_survives_a_save_and_reload(self):
        image = Image(path="C:/img/GMP-000001-XCF.xcf")
        xcf.write_values(image, {"PartNumber": "GMP-000001-XCF"}, gimp=Gimp)
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image,
                       Gio.File.new_for_path(image.get_file().get_path()), None)
        again = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE,
                               Gio.File.new_for_path("C:/img/GMP-000001-XCF.xcf"))
        assert xcf.read_values(again) == {"PartNumber": "GMP-000001-XCF"}

    def test_the_persistent_flag_is_what_makes_that_true(self):
        """Without it a parasite lives only as long as the image is open - and vanishes silently.

        This is the trap the real GIMP API sets, so the fake honours it and this test pins that
        the add-in passes the flag.
        """
        image = Image(path="C:/img/x.xcf")
        image.attach_parasite(Gimp.Parasite.new(xcf.PARASITE, 0, b'{"Revision": "A"}'))
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path("C:/img/x.xcf"), None)
        again = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path("C:/img/x.xcf"))
        assert xcf.read_values(again) == {}

        assert xcf.PERSISTENT_FLAG == fakegimp.PARASITE_PERSISTENT


class TestDrawingOnTheCanvas:
    """Optional, and most images will not use it - but it must not be wrong when they do."""

    def test_a_text_layer_named_for_a_key_takes_the_value(self):
        image = image_with_text_layers("PartNumber", "Revision")
        recorded, drawn = xcf.write_values(
            image, {"PartNumber": "GMP-7", "Revision": "C"}, gimp=Gimp)
        assert (recorded, drawn) == (2, 2)
        assert [l.text for l in image.get_layers()] == ["GMP-7", "C"]

    def test_a_layer_with_no_matching_value_is_left_alone(self):
        image = image_with_text_layers("PartNumber", "Notes")
        xcf.write_values(image, {"PartNumber": "GMP-7"}, gimp=Gimp)
        assert image.get_layers()[1].text == "-"

    def test_a_value_with_no_layer_is_recorded_but_not_drawn(self):
        image = image_with_text_layers("PartNumber")
        recorded, drawn = xcf.write_values(image, {"Cost": "12.00"}, gimp=Gimp)
        assert (recorded, drawn) == (1, 0)
        assert xcf.read_values(image) == {"Cost": "12.00"}

    def test_a_text_layer_inside_a_group_is_found(self):
        """A title block is exactly the thing someone puts in a group."""
        inner = Layer("PartNumber", text="-")
        image = Image(layers=[Layer("Title block", children=[inner])])
        recorded, drawn = xcf.write_values(image, {"PartNumber": "GMP-9"}, gimp=Gimp)
        assert (recorded, drawn) == (1, 1)
        assert inner.text == "GMP-9"

    def test_labelled_keys_lists_what_the_image_can_show(self):
        image = image_with_text_layers("PartNumber", "Revision")
        assert xcf.labelled_keys(image) == ["PartNumber", "Revision"]


class TestWritingIntoAStagedFile:
    def test_the_record_reaches_a_file_nothing_has_open(self):
        path = "C:/staging/GMP-000002-XCF.xcf"
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, Image(path=path),
                       Gio.File.new_for_path(path), None)

        recorded, _drawn = xcf.write_into_file(
            path, {"PartNumber": "GMP-000002-XCF"}, gimp=Gimp, gio=Gio)
        assert recorded == 1

        again = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(path))
        assert xcf.read_values(again) == {"PartNumber": "GMP-000002-XCF"}

    def test_nothing_to_write_touches_nothing(self):
        assert xcf.write_into_file("C:/staging/none.xcf", {}, gimp=Gimp, gio=Gio) == (0, 0)


class TestHowAValueReads:
    def test_an_iso_timestamp_is_drawn_as_a_date(self):
        image = image_with_text_layers("CreationDate")
        xcf.write_values(image, {"CreationDate": "2026-09-28T02:24:15.3456789Z"}, gimp=Gimp)
        assert image.get_layers()[0].text == "2026-09-28"

    def test_but_the_record_keeps_the_exact_value(self):
        image = image_with_text_layers("CreationDate")
        xcf.write_values(image, {"CreationDate": "2026-09-28T02:24:15.3456789Z"}, gimp=Gimp)
        assert parasite_json(image)["CreationDate"] == "2026-09-28T02:24:15.3456789Z"

    def test_anything_else_is_left_exactly_as_it_came(self):
        for value in ["GMP-000002-XCF", "A", "2026", "not-a-date", "", "12.5"]:
            assert xcf.for_display(value) == value
