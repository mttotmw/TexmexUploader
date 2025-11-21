# ============================================================
# modelviewer.py – Texmex Weavers
# Compatible con FreeCAD 1.0.2 Windows
# ============================================================

import os
import tempfile
import FreeCAD

try:
    import FreeCADGui
except:
    FreeCADGui = None

from common import Minio, ENDPOINT, ACCESS_KEY, SECRET_KEY


def _get_temp_dir():
    base = os.path.join(tempfile.gettempdir(), "TexmexLibrary")
    os.makedirs(base, exist_ok=True)
    return base


def _download_temp_file(bucket, key):
    temp_dir = _get_temp_dir()
    local_path = os.path.join(temp_dir, os.path.basename(key))

    client = Minio(
        ENDPOINT,
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        secure=False
    )
    client.fget_object(bucket, key, local_path)
    return local_path


# ============================================================
# Apertura segura + creación manual de GUI view
# ============================================================

def _open_doc_with_gui(path):

    # if no GUI doc exists → activate dummy
    if not FreeCADGui.ActiveDocument:
        try:
            FreeCADGui.activateDocument("TexmexDummy")
        except:
            pass

    # open doc
    doc = FreeCAD.openDocument(path)
    FreeCAD.setActiveDocument(doc.Name)

    try:
        FreeCADGui.activateDocument(doc.Name)
    except:
        pass

    gdoc = FreeCADGui.getDocument(doc.Name)
    if not gdoc:
        FreeCAD.Console.PrintError("No GUI doc\n")
        return doc, None

    view = gdoc.activeView()
    if not view:
        try:
            gdoc.newObject("Gui::View3DInventor", "View")
            view = gdoc.activeView()
        except:
            return doc, None

    return doc, view


# ============================================================
# Generación de preview
# ============================================================

def _generate_fcstd_preview(fcstd_path):

    if not FreeCADGui:
        return None

    # Guardar estado previo
    old_doc = FreeCAD.ActiveDocument
    old_gui_name = None

    try:
        old_gui_name = FreeCADGui.ActiveDocument.Document.Name
    except:
        old_gui_name = None

    # Abrir documento temporal con GUI completa
    doc, view = _open_doc_with_gui(fcstd_path)

    if not doc or not view:
        FreeCAD.Console.PrintError("No se pudo abrir documento para preview.\n")
        return None

    preview_png = os.path.splitext(fcstd_path)[0] + "_preview.png"

    try:
        view.viewIsometric()
        view.fitAll()
        view.saveImage(preview_png, 512, 512, "Current")
    except Exception as e:
        FreeCAD.Console.PrintError(f"Error generando preview: {e}\n")
        preview_png = None

    finally:
        # Cerrar documento temporal
        try:
            FreeCAD.closeDocument(doc.Name)
        except:
            pass

        # Restaurar
        if old_gui_name:
            try:
                FreeCADGui.activateDocument(old_gui_name)
            except:
                pass

    return preview_png if (preview_png and os.path.exists(preview_png)) else None


def generate_preview_for_object(bucket, key):
    ext = os.path.splitext(key)[1].lower()

    try:
        local_path = _download_temp_file(bucket, key)
    except Exception as e:
        FreeCAD.Console.PrintError(f"No se pudo descargar: {e}\n")
        return None

    if ext == ".fcstd":
        return _generate_fcstd_preview(local_path)

    return None
