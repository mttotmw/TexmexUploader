# ============================================================
# InitGui.py - Texmex Workbench (Stable + Submenus + Split Commands)
# ============================================================

import os
import sys
import FreeCAD, FreeCADGui
from PySide2 import QtGui, QtWidgets


# ============================================================
# WORKBENCH CLASS
# ============================================================
class TexmexUploaderWorkbench(FreeCADGui.Workbench):

    MenuText = "Texmex Weavers CAD"
    ToolTip  = "Sube modelos y planos al servidor de Texmex Weavers"

    # Icon
    iconbase = FreeCAD.getUserAppDataDir()
    iconmod  = os.path.join(iconbase, "Mod", "TexmexUploader", "freecad", "Texmex_Uploader")
    Icon     = os.path.join(iconmod, "Resources", "Icons", "boxlogo.svg")

    # ------------------------------------------------------------
    # INITIALIZE WORKBENCH
    # ------------------------------------------------------------
    def Initialize(self):


        # ------------------------------------------------------------
        # PATH DEL MODULO
        # ------------------------------------------------------------
        try:
            mod_path = os.path.dirname(os.path.abspath(__file__))
        except:
            mod_path = os.path.join(
                FreeCAD.getUserAppDataDir(), "Mod", "TexmexUploader", "freecad", "Texmex_Uploader"
            )

        if mod_path not in sys.path:
            sys.path.append(mod_path)

        # ------------------------------------------------------------
        # LOAD COMMANDS
        # ------------------------------------------------------------
        try:
            import model     # model.py
            import svg       # svg.py
            import config    # config.py
            import library   # library.py

            # Register commands
            FreeCADGui.addCommand("UploadModelFile",      model.UploadToTexmexWeaversCmd())
            FreeCADGui.addCommand("UploadCurrentProject", model.UploadCurrentProjectCmd())
            FreeCADGui.addCommand("AddDocAttributes",     model.AddAttributesCMD())
            FreeCADGui.addCommand("UploadTechDrawSVG",    svg.UploadTechDrawSVGCmd())
            FreeCADGui.addCommand("ConfigMinIO",          config.ConfigMinIOCmd())
            FreeCADGui.addCommand("CopyTemplates",        config.CopyTemplatesCmd())
            FreeCADGui.addCommand("AddPageAttributes",    svg.AddPageAttributesCMD())
            FreeCADGui.addCommand("OpenTexmexLibrary",    library.OpenTexmexLibraryCmd())

            # ------------------------------------------------------------
            # TOOLBARS
            # ------------------------------------------------------------
            self.appendToolbar("3D Models", [
                "UploadCurrentProject",
            ])

            self.appendToolbar("SVG Tools", [
                "UploadTechDrawSVG",
            ])

            
            self.appendToolbar("Agregar Attributos del Documento", [
                "AddDocAttributes",
            ])

            self.appendToolbar("Agregar Attributos de Pagina", [
                "AddPageAttributes",
            ])

            self.appendToolbar("Libreria CAD", [
                "OpenTexmexLibrary",
            ])

            # ------------------------------------------------------------
            # MAIN MENU WITH SUBMENUS
            # ------------------------------------------------------------

            self.appendMenu(
                ["Texmex Weavers", "Modelos 3D"],
                [ "UploadCurrentProject","AddDocAttributes"]
            )

            self.appendMenu(
                ["Texmex Weavers", "Planos SVG"],
                ["UploadTechDrawSVG","AddPageAttributes"]
            )

            self.appendMenu(
                ["Texmex Weavers", "Configuración"],
                ["ConfigMinIO", CopyTemplates]
            )

            FreeCAD.Console.PrintMessage(" Texmex Weavers CAD loaded.\n")

        except Exception as e:
            FreeCAD.Console.PrintError(f" Could not load commands: {e}\n")


    def GetClassName(self):
        return "Gui::PythonWorkbench"


# Register Workbench
FreeCADGui.addWorkbench(TexmexUploaderWorkbench())
