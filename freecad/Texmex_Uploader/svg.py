# ============================================================
# svg.py  → Manejo de subida de archivos SVG de TechDraw
# ============================================================

import os
import FreeCAD

# GUI seguro
try:
    import FreeCADGui
    import TechDrawGui
except ImportError:
    FreeCADGui = None
    TechDrawGui = None

# =============================================================================
# IMPORTAR UTILIDADES COMPARTIDAS
# =============================================================================
from common import (
    Minio, S3Error,
    ENDPOINT, ACCESS_KEY, SECRET_KEY,
    BUCKET_SVG,
    show_popup, get_doc_metadata,
    upload_file, list_subfolders,
    join_key, find_etag_path, _slug, _pretty
)

# Qt
try:
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtWidgets


# =============================================================================
# MetadataForm SOLO PARA SVG (más simple que modelos)
# =============================================================================
class MetadataFormSVG(QtWidgets.QDialog):
    """
    Formulario para subir SVG:
     - Área
     - 3 niveles de subcarpetas
     - Descripción y comentario
     - Autolocking cuando se detecta un ETag existente
    """
    def __init__(self, default_name, default_revision="1.00",
                 default_description="", default_comment="", current_etag=None,
                 parent=None, title="Datos del archivo SVG"):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        self.current_etag = current_etag

        layout = QtWidgets.QVBoxLayout(self)

        # ---------------- Nombre ----------------
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Nombre archivo:"))
        self.name_edit = QtWidgets.QLineEdit(default_name)
        row.addWidget(self.name_edit)
        layout.addLayout(row)

        # ---------------- Área ----------------
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Área:"))
        self.area = QtWidgets.QComboBox()
        self.area.addItems([
            "telares circulares",
            "telares de banda",
            "extrusion",
            "laminadora",
            "torre de enfriamiento"
        ])
        row.addWidget(self.area)
        layout.addLayout(row)

        # ---------------- Subcarpetas dinámicas ----------------
        def mkr(label):
            r = QtWidgets.QHBoxLayout()
            r.addWidget(QtWidgets.QLabel(label))
            combo = QtWidgets.QComboBox()
            r.addWidget(combo)
            return r, combo

        row, self.s1 = mkr("Subcarpeta 1:")
        layout.addLayout(row)

        row, self.s2 = mkr("Subcarpeta 2:")
        layout.addLayout(row)

        row, self.s3 = mkr("Subcarpeta 3:")
        layout.addLayout(row)

        def fill1():
            area = _slug(self.area.currentText())
            items = list_subfolders(BUCKET_SVG, area)
            self.s1.clear()
            self.s1.addItems(["<Raíz>"] + items)

        def fill2():
            area = _slug(self.area.currentText())
            s1 = self.s1.currentText()
            self.s2.clear()
            if s1 != "<Raíz>":
                path = f"{area}/{_slug(s1)}"
                items = list_subfolders(BUCKET_SVG, path)
                self.s2.addItems(["<Raíz>"] + items)
            else:
                self.s2.addItem("<Raíz>")

        def fill3():
            area = _slug(self.area.currentText())
            s1, s2 = self.s1.currentText(), self.s2.currentText()
            self.s3.clear()
            if s1 != "<Raíz>" and s2 != "<Raíz>":
                path = f"{area}/{_slug(s1)}/{_slug(s2)}"
                items = list_subfolders(BUCKET_SVG, path)
                self.s3.addItems(["<Raíz>"] + items)
            else:
                self.s3.addItem("<Raíz>")

        self.area.currentIndexChanged.connect(fill1)
        self.s1.currentIndexChanged.connect(fill2)
        self.s2.currentIndexChanged.connect(fill3)

        fill1(); fill2(); fill3()

        # ---------------- Revisión ----------------
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Revisión:"))
        self.rev = QtWidgets.QDoubleSpinBox()
        self.rev.setDecimals(2)
        self.rev.setRange(0, 9999)
        try:
            self.rev.setValue(float(default_revision))
        except:
            self.rev.setValue(1.00)
        row.addWidget(self.rev)
        layout.addLayout(row)

        # ---------------- Descripción / comentario ----------------
        layout.addWidget(QtWidgets.QLabel("Descripción:"))
        self.desc = QtWidgets.QPlainTextEdit(default_description)
        layout.addWidget(self.desc)

        layout.addWidget(QtWidgets.QLabel("Comentario:"))
        self.comment = QtWidgets.QPlainTextEdit(default_comment)
        layout.addWidget(self.comment)

        # ---------------- Botones ----------------
        btn = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok |
                                         QtWidgets.QDialogButtonBox.Cancel)
        btn.accepted.connect(self.accept)
        btn.rejected.connect(self.reject)
        layout.addWidget(btn)

    def get_values(self):
        return {
            "name": self.name_edit.text().strip(),
            "area": self.area.currentText(),
            "s1": self.s1.currentText(),
            "s2": self.s2.currentText(),
            "s3": self.s3.currentText(),
            "revision": float(self.rev.value()),
            "descripcion": self.desc.toPlainText().strip(),
            "comentario": self.comment.toPlainText().strip(),
        }


# =============================================================================
# COMMAND: Upload TechDraw → SVG
# =============================================================================
class UploadTechDrawSVGCmd:
    def GetResources(self):
        return {
            "Pixmap": os.path.join(os.path.dirname(__file__), "./Resources/Icons/fplan.svg"),
            "MenuText": "Subir Página Activa (SVG)",
            "ToolTip": "Exporta y sube la página activa de TechDraw como SVG"
        }

    def Activated(self):
        if not FreeCADGui or not TechDrawGui:
            show_popup("Error", "FreeCAD GUI o TechDraw no disponibles.")
            return

        sel = FreeCADGui.Selection.getSelection()
        if not sel:
            show_popup("Atención", "Selecciona una página de TechDraw.")
            return

        page = sel[0]
        if page.TypeId != "TechDraw::DrawPage":
            show_popup("Atención", "El objeto seleccionado no es una página de TechDraw.")
            return

        # ---- Datos de la página ----
        default_name = getattr(page, "Label", page.Name)
        default_revision = getattr(page, "Base_revision", "1.00")
        default_description = getattr(page, "Base_descripcion", "")
        default_comment = getattr(page, "Base_comment", "")
        current_etag = getattr(page, "Base_etag", None)

        # ---- Exportación temporal ----
        svg_path = os.path.join(os.path.expanduser("~"), f"{default_name}.svg")
        TechDrawGui.exportPageAsSvg(page, svg_path)
        FreeCAD.Console.PrintMessage(f"SVG exportado: {svg_path}\n")

        # ---- Auto-versionado previo ----
        client = Minio(ENDPOINT, ACCESS_KEY, SECRET_KEY, secure=False)
        try:
            dname = default_name.replace(".svg", "")
            proposed = float(default_revision)
            max_rev = proposed

            for obj in client.list_objects(BUCKET_SVG, recursive=True):
                if obj.object_name.endswith(f"/{dname}.svg") or obj.object_name.endswith(f"/{dname}"):
                    meta = client.stat_object(BUCKET_SVG, obj.object_name)
                    rv = float(meta.metadata.get("x-amz-meta-revision", "0"))
                    max_rev = max(max_rev, rv)

            if proposed <= max_rev:
                proposed = round(max_rev + 0.01, 2)

            default_revision = proposed

        except Exception as e:
            FreeCAD.Console.PrintError(f"Auto-version error: {e}\n")

        # ---- Diálogo de metadatos ----
        doc_meta = get_doc_metadata()

        dlg = MetadataFormSVG(
            default_name,
            default_revision,
            default_description,
            default_comment,
            current_etag=current_etag,
            title="Datos del archivo SVG"
        )

        if not dlg.exec():
            return

        data = dlg.get_values()

        # Siempre con extensión .svg
        fname = data["name"]
        if not fname.lower().endswith(".svg"):
            fname = fname + ".svg"

        # ---- Si existe ETag → mantener ruta ----
        if current_etag:
            etag_path = find_etag_path(BUCKET_SVG, current_etag)
        else:
            etag_path = None

        if etag_path:
            parts = etag_path.split("/")
            parts[-1] = fname
            object_name = "/".join(parts)

            area  = parts[0]
            s1 = parts[1] if len(parts) > 1 else ""
            s2 = parts[2] if len(parts) > 2 else ""
            s3 = parts[3] if len(parts) > 3 else ""

        else:
            area = _slug(data["area"])
            s1 = _slug(data["s1"])
            s2 = _slug(data["s2"])
            s3 = _slug(data["s3"])
            object_name = join_key(area, s1, s2, s3, fname)

        # ---- Duplicados ----
        prefix = "/".join(object_name.split("/")[:-1]) + "/"

        same = None
        try:
            for obj in client.list_objects(BUCKET_SVG, prefix=prefix, recursive=False):
                if obj.object_name.endswith(f"/{fname}"):
                    same = obj
                    break
        except Exception as e:
            FreeCAD.Console.PrintError(f"Error búsqueda duplicado: {e}\n")

        if same:
            msg = QtWidgets.QMessageBox()
            msg.setWindowTitle("Archivo duplicado")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setText(
                f"Ya existe un SVG llamado:\n\n{same.object_name}\n\n"
                "¿Actualizar o crear nueva versión?"
            )
            update_btn = msg.addButton("Actualizar", QtWidgets.QMessageBox.AcceptRole)
            version_btn = msg.addButton("Nueva versión", QtWidgets.QMessageBox.ActionRole)
            cancel_btn = msg.addButton("Cancelar", QtWidgets.QMessageBox.RejectRole)
            msg.exec()

            clicked = msg.clickedButton()
            if clicked == cancel_btn:
                return
            elif clicked == version_btn:
                data["revision"] = round(float(data["revision"]) + 0.01, 2)

        # ---- Upload ----
        metadata = {
            "x-amz-meta-revision": str(data["revision"]),
            "x-amz-meta-descripcion": data["descripcion"],
            "x-amz-meta-comment": data["comentario"],
            "x-amz-meta-createdby": doc_meta.get("createdby", ""),
            "x-amz-meta-lastmodifiedby": doc_meta.get("lastmodifiedby", ""),
            "x-amz-meta-company": doc_meta.get("company", "")
        }

        new_etag = upload_file(svg_path, object_name, metadata, bucket=BUCKET_SVG)

        if new_etag:
            if hasattr(page, "Base_etag"):
                page.Base_etag = new_etag
            if hasattr(page, "Base_descripcion"):
                page.Base_descripcion = data["descripcion"]
            if hasattr(page, "Base_comment"):
                page.Base_comment = data["comentario"]
            if hasattr(page, "Base_revision"):
                page.Base_revision = str(data["revision"])

            FreeCAD.ActiveDocument.recompute()
            FreeCAD.ActiveDocument.save()

            show_popup(
                "Éxito",
                f"SVG '{fname}' subido.\n\nRuta final:\n{object_name}\nETag: {new_etag}"
            )

    def IsActive(self):
        return True


# ============================================================
# COMMAND: AddPageAttributesCMD (SVG Pages)
# ============================================================

class AddPageAttributesCMD:
    """
    Crea atributos en páginas TechDraw:
      - Base_comment
      - Base_etag
      - Base_revision
      - Base_descripcion

    Opción C:
      • Si hay una página seleccionada → aplicar SOLO a esa
      • Si NO hay selección → aplicar a TODAS las páginas TechDraw
    """

    REQUIRED = [
        "Base_comment",
        "Base_etag",
        "Base_revision",
        "Base_descripcion"
    ]

    def GetResources(self):
        icon = os.path.join(os.path.dirname(__file__), "Resources/Icons/pProp.svg")
        return {
            "Pixmap": icon,
            "MenuText": "Agregar Atributos a Página",
            "ToolTip": "Crea atributos Base_* en la(s) página(s) de TechDraw"
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        if not doc:
            show_popup("Error", "No hay documento activo.")
            return

        # -----------------------------------------------
        # SELECCIÓN: ¿Hay una página TechDraw seleccionada?
        # -----------------------------------------------
        sel = FreeCADGui.Selection.getSelection()

        selected_pages = []
        for obj in sel:
            if hasattr(obj, "TypeId") and obj.TypeId == "TechDraw::DrawPage":
                selected_pages.append(obj)

        if selected_pages:
            pages = selected_pages
        else:
            # Tomar todas las páginas del documento
            pages = [
                obj for obj in doc.Objects
                if hasattr(obj, "TypeId") and obj.TypeId == "TechDraw::DrawPage"
            ]

        if not pages:
            show_popup("Error", "No se encontraron páginas TechDraw.")
            return

        # -----------------------------------------------
        # PROCESAR CADA PÁGINA
        # -----------------------------------------------
        for page in pages:
            missing = []

            for att in self.REQUIRED:
                if not hasattr(page, att):
                    missing.append(att)

            if not missing:
                # Ya existen todos
                continue

            # Crear los atributos faltantes
            for att in missing:
                try:
                    page.addProperty(
                        "App::PropertyString",
                        att,
                        "Texmex",
                        f"Atributo {att}"
                    )
                    setattr(page, att, "")
                except Exception as e:
                    FreeCAD.Console.PrintError(f"Error agregando {att}: {e}\n")

        # -----------------------------------------------
        # Mensaje final
        # -----------------------------------------------
        if selected_pages:
            show_popup("Completado", "Atributos agregados a la página seleccionada.")
        else:
            show_popup("Completado", "Atributos agregados a todas las páginas TechDraw.")

    def IsActive(self):
        return True
