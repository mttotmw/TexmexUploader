# ============================================================
# config_storage.py → Guardar / cargar config MinIO en XML
# Texmex Weavers CAD
# ============================================================

import os
import xml.etree.ElementTree as ET
import FreeCAD

CONFIG_FILENAME = "config.xml"

def get_config_path():
    """Devuelve la ruta al archivo XML en la carpeta del módulo."""
    module_dir = os.path.dirname(__file__)
    return os.path.join(module_dir, CONFIG_FILENAME)


# ============================================================
# CARGAR CONFIG DESDE XML
# ============================================================

def load_minio_config():
    path = get_config_path()

    # ---------------------------
    # SI NO EXISTE → CREAR DEFAULT
    # ---------------------------
    if not os.path.exists(path):
        save_minio_config(
            endpoint="192.168.88.194:9000",
            access="",
            secret="",
            bucket_model="cad3dfiles",
            bucket_svg="svg"
        )
        return load_minio_config()

    try:
        tree = ET.parse(path)
        root = tree.getroot()

        return {
            "ENDPOINT":     root.findtext("endpoint", ""),
            "ACCESS_KEY":   root.findtext("access_key", ""),
            "SECRET_KEY":   root.findtext("secret_key", ""),
            "BUCKET_MODEL": root.findtext("bucket_model", "cad3dfiles"),
            "BUCKET_SVG":   root.findtext("bucket_svg", "svg")
        }

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error leyendo XML config: {e}\n")
        return {}


# ============================================================
# GUARDAR CONFIG EN XML
# ============================================================

def save_minio_config(endpoint, access, secret, bucket_model, bucket_svg):
    path = get_config_path()

    root = ET.Element("minio_config")
    ET.SubElement(root, "endpoint").text = endpoint
    ET.SubElement(root, "access_key").text = access
    ET.SubElement(root, "secret_key").text = secret
    ET.SubElement(root, "bucket_model").text = bucket_model
    ET.SubElement(root, "bucket_svg").text = bucket_svg

    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)

    FreeCAD.Console.PrintMessage(f"MinIO configuration saved to XML: {path}\n")
