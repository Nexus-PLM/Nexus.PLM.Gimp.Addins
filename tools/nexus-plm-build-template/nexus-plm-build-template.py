#!/usr/bin/env python3
"""Build the GIMP Image template, from inside GIMP.

Only GIMP can write an XCF, so this is a plug-in rather than a script: install it, run
**Nexus PLM ▸ Developer ▸ Build Template**, and it writes the template where
``NEXUS_TEMPLATE_OUT`` says.

    python tools/install_builder.py            # copy this into GIMP's plug-ins directory
    ...run it from the menu once...
    python tools/install_builder.py --remove

Kept out of ``plug-in/`` on purpose: it is a developer tool, and nothing a user installs should
carry a command that overwrites a template.

**The template is deliberately plain** - one white layer and nothing else. Marc, Sep 28 2026:
*"the user will never render the attribute data in their image but at least its mapped into the
file thats the important thing"*. The PLM record lives in the image's parasite, which the add-in
writes and which travels inside the ``.xcf``; a title block drawn on the canvas would be
decoration nobody asked for. An image that wants to show a value can still add a text layer named
after the attribute, and the add-in will fill it - but the template does not presume it.

Any traceback goes to ``nexus_template_build.log`` beside the output, because a plug-in that
fails inside GIMP otherwise fails in silence.
"""

import os
import sys
import traceback

import gi

gi.require_version("Gimp", "3.0")
from gi.repository import Gimp                                          # noqa: E402
from gi.repository import Gio                                           # noqa: E402
from gi.repository import GLib                                          # noqa: E402

WIDTH, HEIGHT = 1200, 900

DEFAULT_OUT = os.path.join(
    os.environ.get("USERPROFILE", os.path.expanduser("~")), "GIMP Image.xcf")


def build(procedure, run_mode, image, drawables, config, run_data):
    out = os.environ.get("NEXUS_TEMPLATE_OUT", DEFAULT_OUT)
    try:
        os.makedirs(os.path.dirname(out), exist_ok=True)

        made = Gimp.Image.new(WIDTH, HEIGHT, Gimp.ImageBaseType.RGB)
        layer = Gimp.Layer.new(made, "Artwork", WIDTH, HEIGHT,
                               Gimp.ImageType.RGB_IMAGE, 100.0, Gimp.LayerMode.NORMAL)
        made.insert_layer(layer, None, 0)
        layer.fill(Gimp.FillType.WHITE)

        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, made, Gio.File.new_for_path(out), None)
        made.delete()

        Gimp.message("Nexus PLM template written to %s" % out)
    except Exception:
        report = os.path.join(os.path.dirname(out) or ".", "nexus_template_build.log")
        try:
            with open(report, "w", encoding="utf-8") as handle:
                handle.write(traceback.format_exc())
        except Exception:
            pass
        Gimp.message("Nexus PLM template build FAILED - see %s" % report)

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class BuildTemplate(Gimp.PlugIn):
    def do_query_procedures(self):
        return ["nexus-plm-build-template"]

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, build, None)
        procedure.set_image_types("*")
        procedure.set_menu_label("Build Template")
        procedure.add_menu_path("<Image>/Nexus PLM/Developer/")
        procedure.set_documentation("Build the Nexus PLM GIMP Image template", "", name)
        procedure.set_attribution("Nexus PLM", "Nexus PLM", "2026")
        return procedure


Gimp.main(BuildTemplate.__gtype__, sys.argv)
