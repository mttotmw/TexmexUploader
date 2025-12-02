# ============================================================
# config.py
# ============================================================

import FreeCAD, FreeCADGui, os
from PySide2 import QtWidgets, QtCore

from config_storage import load_minio_config, save_minio_config


class MinIOConfigDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Texmex Weavers Configuración del Servidor S3")
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)

        # 1. Cargar valores desde XML
        cfg = load_minio_config()

        layout = QtWidgets.QFormLayout(self)

        # Campos
        self.endpoint_le = QtWidgets.QLineEdit(cfg.get("ENDPOINT", ""))
        self.access_le   = QtWidgets.QLineEdit(cfg.get("ACCESS_KEY", ""))
        self.secret_le   = QtWidgets.QLineEdit(cfg.get("SECRET_KEY", ""))
        self.secret_le.setEchoMode(QtWidgets.QLineEdit.Password)
        self.model_bucket_le = QtWidgets.QLineEdit(cfg.get("BUCKET_MODEL", "cad3dfiles"))
        self.svg_bucket_le   = QtWidgets.QLineEdit(cfg.get("BUCKET_SVG", "svg"))

        # Add widgets
        layout.addRow("MinIO Endpoint (IP:Port):", self.endpoint_le)
        layout.addRow("Access Key:", self.access_le)
        layout.addRow("Secret Key:", self.secret_le)
        layout.addRow("Model Bucket Name:", self.model_bucket_le)
        layout.addRow("SVG Bucket Name:", self.svg_bucket_le)

        # Buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def accept(self):
        save_minio_config(
            self.endpoint_le.text(),
            self.access_le.text(),
            self.secret_le.text(),
            self.model_bucket_le.text(),
            self.svg_bucket_le.text()
        )
        super().accept()


class ConfigMinIOCmd:
    ICON_SVG = os.path.join(os.path.dirname(__file__), "Resources/Icons/setting.svg")

    def GetResources(self):
        return {
            "Pixmap": self.ICON_SVG,
            "MenuText": "Configurar Servidor",
            "ToolTip":  "Configurar conexión S3"
        }

    def Activated(self):
        dlg = MinIOConfigDialog()
        dlg.exec_()

    def IsActive(self):
        return True
    
# ============================================================
# COPY TEMPLATES COMMAND
# ============================================================

class CopyTemplatesCmd:
    ICON_SVG = os.path.join(os.path.dirname(__file__), "Resources/Icons/boxlogo.svg")

    def GetResources(self):
        return {
            "Pixmap": self.ICON_SVG,
            "MenuText": "Instalar Plantillas Texmex",
            "ToolTip":  "Copia todas las plantillas SVG a TechDraw/Templates"
        }

    def Activated(self):
        try:
            mod_path = os.path.dirname(os.path.abspath(__file__))
            src_folder = os.path.join(mod_path, "Resources", "templates")

            # TechDraw folder
            dest_folder = os.path.join(
                FreeCAD.getUserAppDataDir(),
                "Mod",
                "TechDraw",
                "Templates"
            )

            if not os.path.exists(dest_folder):
                os.makedirs(dest_folder)

            copied = 0
            for file in os.listdir(src_folder):
                if file.lower().endswith(".svg"):
                    src = os.path.join(src_folder, file)
                    dest = os.path.join(dest_folder, file)
                    QtCore.QFile.copy(src, dest)
                    copied += 1

            FreeCAD.Console.PrintMessage(
                f"\n✔ Se copiaron {copied} plantillas a TechDraw/Templates.\n"
            )
            QtWidgets.QMessageBox.information(
                None,
                "Plantillas Instaladas",
                f"Se copiaron {copied} plantillas Texmex a:\n{dest_folder}"
            )

        except Exception as e:
            FreeCAD.Console.PrintError(f"\n❌ Error copiando plantillas: {e}\n")
            QtWidgets.QMessageBox.critical(
                None, "Error", f"No se pudieron copiar las plantillas:\n{e}"
            )

    def IsActive(self):
        return True

