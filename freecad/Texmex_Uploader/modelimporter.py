# ============================================================
# modelimporter.py
# Texmex Weavers – FreeCAD Integration
# ============================================================

import os
import tempfile
import FreeCAD

try:
    import FreeCADGui
except ImportError:
    FreeCADGui = None

from common import Minio, ENDPOINT, ACCESS_KEY, SECRET_KEY, show_popup


def _get_temp_dir():
    base = os.path.join(tempfile.gettempdir(), "TexmexLibrary")
    if not os.path.exists(base):
        os.makedirs(base, exist_ok=True)
    return base


def download_model_to_temp(bucket, key):
    """
    Descarga el archivo MinIO (key) a un archivo temporal.
    """
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


def open_model_as_new(bucket, key):
    try:
        local_path = download_model_to_temp(bucket, key)
        doc = FreeCAD.openDocument(local_path)

        # ========================================================
        # EXTRAER ETag real del archivo descargado
        # ========================================================
        client = Minio(ENDPOINT, access_key=ACCESS_KEY, secret_key=SECRET_KEY, secure=False)
        stat = client.stat_object(bucket, key)
        etag = getattr(stat, "etag", "")

        # Guardar atributos en el documento
        try:
            doc.Base_etag = etag
            doc.Base_comment = ""
            doc.Base_descripcion = ""
            doc.Base_revision = "1.00"
            doc.recompute()
            doc.save()
        except Exception as e:
            FreeCAD.Console.PrintError(f"No se pudieron asignar atributos: {e}\n")

        if FreeCADGui:
            FreeCADGui.SendMsgToActiveView("ViewFit")

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error abriendo modelo: {e}\n")
        show_popup("Error", f"No se pudo abrir el modelo:\n{e}")


def import_model_into_current(bucket, key):
    """
    Importa todos los objetos de un archivo .FCStd al documento actual.
    """
    cur_doc = FreeCAD.ActiveDocument
    if not cur_doc:
        # Si no hay documento, abrimos uno nuevo y ahí importamos
        cur_doc = FreeCAD.newDocument("Importado")
        if FreeCADGui:
            FreeCADGui.SendMsgToActiveView("ViewFit")

    try:
        local_path = download_model_to_temp(bucket, key)

        src_doc = FreeCAD.openDocument(local_path)

        # Copiamos todos los objetos del doc fuente al actual
        for obj in src_doc.Objects:
            try:
                cur_doc.copyObject(obj)
            except Exception as e:
                FreeCAD.Console.PrintError(f"No se pudo copiar objeto {obj.Name}: {e}\n")

        cur_doc.recompute()
        
        # ========================================================
        # Actualizar ETag del documento actual al importar
        # ========================================================
        try:
            stat = client.stat_object(bucket, key)
            etag = getattr(stat, "etag", "")

            cur_doc.Base_etag = etag
            cur_doc.Base_revision = "1.00"  # o lo que ocupes
            cur_doc.Base_descripcion = ""
            cur_doc.Base_comment = ""

            cur_doc.recompute()
            cur_doc.save()

        except Exception as e:
            FreeCAD.Console.PrintError(f"No se pudo actualizar atributos del doc actual: {e}\n")


        # Cerrar documento fuente
        try:
            FreeCAD.closeDocument(src_doc.Name)
        except Exception:
            pass

        if FreeCADGui:
            FreeCADGui.SendMsgToActiveView("ViewFit")

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error importando modelo: {e}\n")
        show_popup("Error", f"No se pudo importar el modelo:\n{e}")


def delete_model_from_bucket(bucket, key):
    """
    Elimina un archivo del bucket. Devuelve True si tuvo éxito.
    """
    try:
        client = Minio(
            ENDPOINT,
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY,
            secure=False
        )
        client.remove_object(bucket, key)
        return True
    except Exception as e:
        FreeCAD.Console.PrintError(f"Error eliminando modelo: {e}\n")
        show_popup("Error", f"No se pudo eliminar el modelo:\n{e}")
        return False
