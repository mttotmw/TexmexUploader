# ============================================================
# common.py → Texmex Weavers FreeCAD Integration
# ============================================================

import os, sys, subprocess
import FreeCAD

# Qt seguro
try:
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

# ============================================================
# Lee XML
# ============================================================

from config_storage import load_minio_config

cfg = load_minio_config()

ENDPOINT     = cfg.get("ENDPOINT", "")
ACCESS_KEY   = cfg.get("ACCESS_KEY", "")
SECRET_KEY   = cfg.get("SECRET_KEY", "")

BUCKET_MODEL = cfg.get("BUCKET_MODEL", "cad3dfiles")
BUCKET_SVG   = cfg.get("BUCKET_SVG", "svg")



# ============================================================
# AUTO-INSTALAR MINIO
# ============================================================

def ensure_minio_installed():
    try:
        from minio import Minio
        from minio.error import S3Error
        return Minio, S3Error
    except ImportError:
        try:
            python_exe = os.path.join(os.path.dirname(sys.executable), "python.exe")
            if not os.path.exists(python_exe):
                python_exe = sys.executable
            subprocess.check_call([python_exe, "-m", "pip", "install", "--user", "minio"])
            from minio import Minio
            from minio.error import S3Error
            return Minio, S3Error
        except Exception as e:
            FreeCAD.Console.PrintError(f"Error instalando minio: {e}\n")
            return None, None

Minio, S3Error = ensure_minio_installed()


# ============================================================
# POPUP
# ============================================================

def show_popup(title, text, icon=QtWidgets.QMessageBox.Information):
    msg = QtWidgets.QMessageBox()
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(icon)
    msg.exec()


# ============================================================
# SLUG / PRETTY HELPERS
# ============================================================

def _slug(txt: str):
    if not txt:
        return ""
    return txt.strip().replace(" ", "_").replace("/", "_")

def _pretty(txt: str):
    if not txt:
        return ""
    return txt.replace("_", " ")


# ============================================================
# SUBCARPETAS (NIVEL DIRECTO)
# ============================================================

def list_subfolders(bucket: str, prefix=""):
    """
    Devuelve subcarpetas DIRECTAS bajo prefix.
    Ej: "telares_circulares" → ["motores", "guias"]
    """
    try:
        client = Minio(ENDPOINT, ACCESS_KEY, SECRET_KEY, secure=False)
        if not client.bucket_exists(bucket):
            return []

        base = prefix.strip("/")
        base = base + "/" if base else ""

        subs = set()

        for obj in client.list_objects(bucket, prefix=base, recursive=False):
            key = obj.object_name[len(base):]
            if "/" in key:
                folder = key.split("/", 1)[0]
                subs.add(folder)

        return sorted(_pretty(s) for s in subs)

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error leyendo subcarpetas {prefix}: {e}\n")
        return []


# ============================================================
# BUSCAR RUTA POR ETAG
# ============================================================

def find_etag_path(bucket: str, etag: str):
    if not etag:
        return None

    try:
        client = Minio(ENDPOINT, ACCESS_KEY, SECRET_KEY, secure=False)

        for obj in client.list_objects(bucket, recursive=True):
            oetag = (getattr(obj, "etag", "") or "").strip('"').lower()
            if etag.strip('"').lower() == oetag:
                return obj.object_name

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error buscando ETag: {e}\n")

    return None


# ============================================================
# CONSTRUIR RUTA MINIO
# ============================================================

def join_key(area, s1, s2, s3, filename):
    parts = []
    if area: parts.append(_slug(area))
    if s1:   parts.append(_slug(s1))
    if s2:   parts.append(_slug(s2))
    if s3:   parts.append(_slug(s3))
    parts.append(filename)
    return "/".join(parts)


# ============================================================
# METADATA DE FREECAD
# ============================================================

def get_doc_metadata(doc=None):
    try:
        if not doc:
            doc = FreeCAD.ActiveDocument
        if not doc:
            return {}

        data = {}

        # cargamos valores SI existen, si no → fallback "" / 1.00
        data["descripcion"] = getattr(doc, "Base_descripcion", "") or ""
        data["comment"]     = getattr(doc, "Base_comment", "") or ""
        data["revision"]    = getattr(doc, "Base_revision", "1.00") or "1.00"
        data["etag"]        = getattr(doc, "Base_etag", "")

        return data

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error metadata: {e}\n")
        return {}


# ============================================================
# SUBIR ARCHIVO
# ============================================================

def upload_file(filepath, object_name, metadata=None, bucket=BUCKET_MODEL):
    try:
        client = Minio(ENDPOINT, ACCESS_KEY, SECRET_KEY, secure=False)

        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

        result = client.fput_object(
            bucket,
            object_name,
            filepath,
            metadata=metadata
        )

        return getattr(result, "etag", None)

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error subiendo objeto: {e}\n")
        show_popup("Error", f"No se pudo subir:\n{e}",
                   QtWidgets.QMessageBox.Critical)
        return None
