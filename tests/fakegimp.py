"""A GIMP small enough to test against.

The add-in's own logic - what goes in the parasite, which layers get written, what a command does
when the item is not registered - has nothing to do with GIMP's C library, and testing it should
not need a running GIMP. So the pieces the code actually touches are stood up here: an image with
parasites and layers, a ``Parasite`` that remembers its bytes, and a ``file_save``/``file_load``
pair backed by a dict.

It is deliberately faithful about the one thing that matters: a parasite is only persisted when
it carries the persistent flag, which is the trap the real API sets.
"""

import json

PARASITE_PERSISTENT = 1


class Parasite:
    def __init__(self, name, flags, data):
        self.name = name
        self.flags = flags
        self._data = bytes(data)

    @staticmethod
    def new(name, flags, data):
        return Parasite(name, flags, data)

    def get_data(self):
        return self._data


class Layer:
    def __init__(self, name, text=None, children=None):
        self._name = name
        self._text = text
        self._children = children or []

    def get_name(self):
        return self._name

    def is_text_layer(self):
        return self._text is not None

    def is_group(self):
        return bool(self._children)

    def get_children(self):
        return self._children

    def set_text(self, value):
        if self._text is None:
            raise TypeError("not a text layer")
        self._text = value

    @property
    def text(self):
        return self._text


class Image:
    def __init__(self, layers=None, path=None):
        self._parasites = {}
        self._layers = layers or []
        self._path = path
        self.deleted = False

    # ── parasites ────────────────────────────────────────────────────────────

    def attach_parasite(self, parasite):
        self._parasites[parasite.name] = parasite

    def get_parasite(self, name):
        return self._parasites.get(name)

    def get_parasite_list(self):
        return list(self._parasites)

    # ── layers and file ──────────────────────────────────────────────────────

    def get_layers(self):
        return self._layers

    def get_file(self):
        return GioFile(self._path) if self._path else None

    def delete(self):
        self.deleted = True


class GioFile:
    def __init__(self, path):
        self._path = path

    def get_path(self):
        return self._path

    @staticmethod
    def new_for_path(path):
        return GioFile(path)


class Gio:
    File = GioFile


class RunMode:
    NONINTERACTIVE = 0


class Gimp:
    """Stands in for ``gi.repository.Gimp`` - only what the add-in calls."""

    Parasite = Parasite
    RunMode = RunMode
    PARASITE_PERSISTENT = PARASITE_PERSISTENT

    #: path -> the image saved there, so file_load can give it back.
    saved = {}

    @staticmethod
    def file_save(run_mode, image, gio_file, options):
        # Only persistent parasites reach the file. This is the real API's behaviour and the
        # whole reason the flag is passed at all.
        stored = Image(layers=image.get_layers(), path=gio_file.get_path())
        for name, parasite in image._parasites.items():
            if parasite.flags & PARASITE_PERSISTENT:
                stored.attach_parasite(Parasite(name, parasite.flags, parasite.get_data()))
        Gimp.saved[gio_file.get_path()] = stored

    @staticmethod
    def file_load(run_mode, gio_file):
        path = gio_file.get_path()
        if path not in Gimp.saved:
            raise RuntimeError("no such file: %s" % path)
        source = Gimp.saved[path]
        copy = Image(layers=source.get_layers(), path=path)
        for name, parasite in source._parasites.items():
            copy.attach_parasite(Parasite(name, parasite.flags, parasite.get_data()))
        return copy

    @staticmethod
    def message(text):
        Gimp.messages.append(text)

    messages = []


def reset():
    Gimp.saved = {}
    Gimp.messages = []


def parasite_json(image, name="nexus-plm/attributes"):
    """The parasite's payload, decoded - a convenience for assertions."""
    parasite = image.get_parasite(name)
    return None if parasite is None else json.loads(bytes(parasite.get_data()).decode("utf-8"))
