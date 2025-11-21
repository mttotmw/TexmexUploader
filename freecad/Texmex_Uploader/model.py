# ============================================================
# model.py → Manejo de archivos FCStd: Upload & MetadataDialog
# Texmex Weavers – FreeCAD Integration
# ============================================================

import os, sys, subprocess
import FreeCAD

# GUI
try:
    import FreeCADGui
except:
    FreeCADGui = None

# Qt seguro
try:
    from PySide6 import QtWidgets, QtCore
except:
    from PySide2 import QtWidgets, QtCore

# Common utilities
from common import (
    Minio, S3Error,
    ENDPOINT, ACCESS_KEY, SECRET_KEY,
    BUCKET_MODEL,
    show_popup, get_doc_metadata,
    upload_file, list_subfolders,
    find_etag_path, join_key, _slug, _pretty
)


# ============================================================
# CLEAN HELPERS
# ============================================================

def clean_segment(v):
    if v in (None, "", "<Raíz>"):
        return ""
    return v.strip()


def clean_path(*parts):
    out = [clean_segment(p) for p in parts if clean_segment(p)]
    return "/".join(out)


# ============================================================
# METADATA FORM DIALOG
# ============================================================

class MetadataForm(QtWidgets.QDialog):
    """
    Formulario que permite editar:
      • Nombre
      • Área
      • Subcarpeta 1/2/3
      • Descripción
      • Comentario
      • Revisión
    - Si existe ETag → ruta se bloquea
    - Si no hay ETag → ruta editable
    """
    def __init__(self, meta, parent=None, title="Datos del archivo"):
        super().__init__(parent)

        self.meta = meta
        self.setWindowTitle(title)
        self.setMinimumWidth(520)

        main = QtWidgets.QVBoxLayout(self)

        # ------------------------------
        # NOMBRE
        # ------------------------------
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Nombre:"))
        self.name_edit = QtWidgets.QLineEdit(meta.get("name", ""))
        row.addWidget(self.name_edit)
        main.addLayout(row)

        # ------------------------------
        # CHECKBOX EDITAR RUTA
        # ------------------------------
        self.chk_edit = QtWidgets.QCheckBox("Editar ruta")
        main.addWidget(self.chk_edit)

        # ------------------------------
        # ÁREA
        # ------------------------------
        rowA = QtWidgets.QHBoxLayout()
        rowA.addWidget(QtWidgets.QLabel("Área:"))
        self.area_combo = QtWidgets.QComboBox()
        self.area_combo.addItems([
            "telares circulares",
            "telares de banda",
            "extrusion",
            "laminadora",
            "torre de enfriamiento",
        ])
        rowA.addWidget(self.area_combo)
        main.addLayout(rowA)

        # ============================================================
        # SUBCARPETAS (3 niveles con “crear nuevo”)
        # ============================================================

        def mk_row(label):
            w = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(w)
            h.setContentsMargins(0,0,0,0)
            h.addWidget(QtWidgets.QLabel(label))

            combo = QtWidgets.QComboBox()
            combo.addItems(["<Raíz>", "<Crear nuevo…>"])
            edit = QtWidgets.QLineEdit()
            edit.setPlaceholderText("Nombre nueva carpeta…")
            edit.setVisible(False)

            h.addWidget(combo)
            h.addWidget(edit)

            def on_change(_):
                new = combo.currentText() == "<Crear nuevo…>"
                edit.setVisible(new)
                if not new:
                    edit.clear()
                self._refresh_visibility()

            combo.currentIndexChanged.connect(on_change)
            return w, combo, edit

        self.s1_row, self.s1, self.s1_new = mk_row("Subcarpeta 1:")
        self.s2_row, self.s2, self.s2_new = mk_row("Subcarpeta 2:")
        self.s3_row, self.s3, self.s3_new = mk_row("Subcarpeta 3:")

        main.addWidget(self.s1_row)
        main.addWidget(self.s2_row)
        main.addWidget(self.s3_row)

        # ============================================================
        # FILLERS DINÁMICOS
        # ============================================================

        def fill_s1():
            area_slug = _slug(self.area_combo.currentText())
            folders = list_subfolders(BUCKET_MODEL, area_slug)

            self.s1.blockSignals(True)
            self.s1.clear()
            self.s1.addItems(["<Raíz>", "<Crear nuevo…>"] + folders)
            self.s1.blockSignals(False)
            self._refresh_visibility()

        def fill_s2():
            area_slug = _slug(self.area_combo.currentText())
            s1txt = clean_segment(self.s1.currentText())
            prefix = f"{area_slug}/{_slug(s1txt)}" if s1txt else ""

            self.s2.blockSignals(True)
            self.s2.clear()
            self.s2.addItems(["<Raíz>", "<Crear nuevo…>"])
            if prefix:
                self.s2.addItems(list_subfolders(BUCKET_MODEL, prefix))
            self.s2.blockSignals(False)
            self._refresh_visibility()

        def fill_s3():
            area_slug = _slug(self.area_combo.currentText())
            s1txt = clean_segment(self.s1.currentText())
            s2txt = clean_segment(self.s2.currentText())

            prefix = ""
            if s1txt and s2txt:
                prefix = f"{area_slug}/{_slug(s1txt)}/{_slug(s2txt)}"

            self.s3.blockSignals(True)
            self.s3.clear()
            self.s3.addItems(["<Raíz>", "<Crear nuevo…>"])
            if prefix:
                self.s3.addItems(list_subfolders(BUCKET_MODEL, prefix))
            self.s3.blockSignals(False)
            self._refresh_visibility()

        self.area_combo.currentIndexChanged.connect(fill_s1)
        self.s1.currentIndexChanged.connect(fill_s2)
        self.s2.currentIndexChanged.connect(fill_s3)

        # Primera carga
        fill_s1()
        fill_s2()
        fill_s3()

        # ============================================================
        # AUTO-CARGA DE RUTA DESDE meta["ruta"]
        # ============================================================

        ruta = meta.get("ruta", {}) or {}

        # ---------- ÁREA ----------
        if ruta.get("area"):
            pretty_area = _pretty(ruta["area"])
            if pretty_area not in [self.area_combo.itemText(i) for i in range(self.area_combo.count())]:
                self.area_combo.addItem(pretty_area)
            self.area_combo.setCurrentText(pretty_area)

        # Recargar sub1 
        fill_s1()

        # ---------- SUBCARPETA 1 ----------
        if ruta.get("s1"):
            pretty_s1 = _pretty(ruta["s1"])
            items = [self.s1.itemText(i) for i in range(self.s1.count())]
            if pretty_s1 not in items:
                self.s1.addItem(pretty_s1)
            self.s1.setCurrentText(pretty_s1)

        fill_s2()

        # ---------- SUBCARPETA 2 ----------
        if ruta.get("s2"):
            pretty_s2 = _pretty(ruta["s2"])
            items = [self.s2.itemText(i) for i in range(self.s2.count())]
            if pretty_s2 not in items:
                self.s2.addItem(pretty_s2)
            self.s2.setCurrentText(pretty_s2)

        fill_s3()

        # ---------- SUBCARPETA 3 ----------
        if ruta.get("s3"):
            pretty_s3 = _pretty(ruta["s3"])
            items = [self.s3.itemText(i) for i in range(self.s3.count())]
            if pretty_s3 not in items:
                self.s3.addItem(pretty_s3)
            self.s3.setCurrentText(pretty_s3)


        self._refresh_visibility()

        # ============================================================
        # BLOQUEAR RUTA SI YA EXISTE ETAG
        # ============================================================

        has_route = ruta.get("area") or ruta.get("s1") or ruta.get("s2") or ruta.get("s3")
        self.chk_edit.setChecked(not has_route)

        def toggle(_):
            en = self.chk_edit.isChecked()
            for w in (self.area_combo, self.s1, self.s1_new,
                      self.s2, self.s2_new, self.s3, self.s3_new):
                w.setEnabled(en)

        toggle(0)
        self.chk_edit.stateChanged.connect(toggle)

        # ============================================================
        # REVISIÓN
        # ============================================================

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Revisión:"))
        self.rev = QtWidgets.QDoubleSpinBox()
        self.rev.setReadOnly(True)
        self.rev.setDecimals(2)
        self.rev.setRange(0, 9999)
        try:
            self.rev.setValue(float(meta.get("revision", 1.00)))
        except:
            self.rev.setValue(1.00)
        row.addWidget(self.rev)
        main.addLayout(row)

        # ============================================================
        # DESCRIPCIÓN Y COMENTARIO
        # ============================================================

        main.addWidget(QtWidgets.QLabel("Descripción:"))
        self.desc = QtWidgets.QPlainTextEdit(meta.get("descripcion", ""))
        main.addWidget(self.desc)

        main.addWidget(QtWidgets.QLabel("Comentario:"))
        self.comment = QtWidgets.QPlainTextEdit(meta.get("comment", ""))
        main.addWidget(self.comment)

        # Botones
        b = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        main.addWidget(b)

    # ----------------------------------------------------------
    # Show/Hide niveles
    # ----------------------------------------------------------
    def _refresh_visibility(self):
        s1 = self.s1.currentText()
        s2 = self.s2.currentText()

        show2 = s1 not in ("", "<Raíz>")
        show3 = show2 and s2 not in ("", "<Raíz>")

        self.s2_row.setVisible(show2)
        self.s3_row.setVisible(show3)

    # ----------------------------------------------------------
    # Obtener datos limpios
    # ----------------------------------------------------------
    def get_values(self):

        def pick(combo, edit):
            if combo.currentText() == "<Crear nuevo…>":
                return clean_segment(edit.text())
            return clean_segment(combo.currentText())

        return {
            "name": self.name_edit.text().strip(),
            "area": pick(self.area_combo, None),
            "s1": pick(self.s1, self.s1_new),
            "s2": pick(self.s2, self.s2_new),
            "s3": pick(self.s3, self.s3_new),

            "revision": float(self.rev.value()),
            "descripcion": self.desc.toPlainText().strip(),
            "comment": self.comment.toPlainText().strip(),

            "editar_ruta": self.chk_edit.isChecked()
        }

# ============================================================
# SUBIR ARCHIVO FCStd MANUALMENTE (CORREGIDO)
# ============================================================

class UploadToTexmexWeaversCmd:

    def GetResources(self):
        icon = os.path.join(os.path.dirname(__file__), "Resources/Icons/folder.svg")
        return {
            "Pixmap": icon,
            "MenuText": "Subir Modelo FCStd",
            "ToolTip": "Sube un archivo .FCStd a MinIO con metadatos"
        }

    def Activated(self):
        parent = FreeCADGui.getMainWindow() if FreeCADGui else None

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            parent,
            "Selecciona archivo FCStd",
            os.path.expanduser("~"),
            "FreeCAD (*.FCStd)"
        )
        if not path:
            return

        # --------------------------------------------------------
        # METADATA LOCAL
        # --------------------------------------------------------
        doc_meta = get_doc_metadata()
        etag_doc = doc_meta.get("etag", "")

        try:
            old_rev = float(doc_meta.get("revision", 1.00))
        except:
            old_rev = 1.00

        # new_rev siempre definido
        new_rev = old_rev

        ruta = {"area": "", "s1": "", "s2": "", "s3": ""}

        # --------------------------------------------------------
        # BUSCAR RUTA POR ETAG (si existe)
        # --------------------------------------------------------
        etag_path = find_etag_path(BUCKET_MODEL, etag_doc)

        if etag_doc and etag_path:
            parts = etag_path.split("/")

            # Quitar filename final
            if len(parts) > 0:
                parts = parts[:-1]

            if len(parts) >= 1: ruta["area"] = _pretty(parts[0])
            if len(parts) >= 2: ruta["s1"]   = _pretty(parts[1])
            if len(parts) >= 3: ruta["s2"]   = _pretty(parts[2])
            if len(parts) >= 4: ruta["s3"]   = _pretty(parts[3])

            # Auto-incrementar revisión solo si ya existe archivo
            new_rev = round(old_rev + 0.01, 2)

        # --------------------------------------------------------
        # PREPARAR METADATA PARA EL DIALOGO
        # --------------------------------------------------------
        meta = {
            "name": os.path.basename(path),
            "descripcion": doc_meta.get("descripcion", ""),
            "comment":     doc_meta.get("comment", ""),
            "revision":    new_rev,
            "etag":        etag_doc,
            "ruta":        ruta
        }

        dlg = MetadataForm(meta, title="Datos del archivo FCStd")
        if not dlg.exec():
            return

        data = dlg.get_values()

        # Si el usuario no edita ruta → restaurar ruta detectada
        if not data["editar_ruta"]:
            data.update(ruta)

        # Nombre final del objeto en MinIO
        object_name = join_key(
            data["area"], data["s1"], data["s2"], data["s3"], data["name"]
        )

        # --------------------------------------------------------
        # PERMITIR reemplazo (no bloquear por ETag existente)
        # --------------------------------------------------------
        metadata = {
            "x-amz-meta-revision": str(data["revision"]),
            "x-amz-meta-descripcion": data["descripcion"],
            "x-amz-meta-comment": data["comment"]
        }
        
        # ============================================================
        # GUARDAR DOCUMENTO ANTES DE SUBIR
        # ============================================================
        try:
            if doc and doc.FileName:
                doc.recompute()
                if FreeCADGui:
                    # Guardado real, idéntico a darle click al botón de guardar
                    FreeCADGui.runCommand("Std_Save", 0)
                else:
                    # Modo sin interfaz (testing / headless)
                    doc.save()

        except Exception as e:
            FreeCAD.Console.PrintError(f"No se pudo guardar antes de subir: {e}\n")

        # Subir archivo al bucket
        
        etag = upload_file(path, object_name, metadata, BUCKET_MODEL)

        # --------------------------------------------------------
        # SI SUBIÓ BIEN
        # --------------------------------------------------------
        if etag:
            show_popup(
                "Completado",
                f"Archivo subido:\n{object_name}\nETag: {etag}"
            )

# ============================================================
# SUBIR DOCUMENTO ACTIVO
# ============================================================

class UploadCurrentProjectCmd:

    def GetResources(self):
        icon = os.path.join(os.path.dirname(__file__), "Resources/Icons/export.svg")
        return {
            "Pixmap": icon,
            "MenuText": "Subir Proyecto Actual",
            "ToolTip": "Sube el FCStd activo usando sus metadatos"
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        if not doc or not doc.FileName:
            show_popup("Error", "No hay documento activo guardado.")
            return

        # -----------------------------
        # METADATA ACTUAL DEL DOCUMENTO
        # -----------------------------
        doc_meta = get_doc_metadata(doc)
        etag_doc = doc_meta.get("etag", "")

        # Revision actual del doc
        try:
            old_rev = float(doc_meta.get("revision", 1.00))
        except:
            old_rev = 1.00

        # new_rev siempre definido
        new_rev = old_rev
        ruta = {"area": "", "s1": "", "s2": "", "s3": ""}

        # --------------------------------------------------------
        # SI EXISTE ETag → buscar ruta y auto-incrementar versión
        # --------------------------------------------------------
        etag_path = find_etag_path(BUCKET_MODEL, etag_doc)

        if etag_doc and etag_path:
            # camino tipo: area/s1/s2/s3/name.FCStd
            parts = etag_path.split("/")

            # quitar filename
            if len(parts) > 0:
                parts = parts[:-1]

            if len(parts) >= 1: ruta["area"] = _pretty(parts[0])
            if len(parts) >= 2: ruta["s1"]   = _pretty(parts[1])
            if len(parts) >= 3: ruta["s2"]   = _pretty(parts[2])
            if len(parts) >= 4: ruta["s3"]   = _pretty(parts[3])

            # auto-incremento SOLO si ya existía
            new_rev = round(old_rev + 0.01, 2)

        # --------------------------------------------------------
        # METADATA PARA EL FORM
        # --------------------------------------------------------
        meta = {
            "name": os.path.basename(doc.FileName),
            "descripcion": doc_meta.get("descripcion", ""),
            "comment":     doc_meta.get("comment", ""),
            "revision":    new_rev,     # <-- ya corregido
            "etag":        etag_doc,
            "ruta":        ruta
        }

        dlg = MetadataForm(meta, title="Datos del Proyecto Actual")
        if not dlg.exec():
            return

        data = dlg.get_values()

        # Si no se permite editar ruta → restaurar ruta original
        if not data["editar_ruta"]:
            data.update(ruta)

        # Construir el nombre final del objeto
        object_name = join_key(
            data["area"], data["s1"], data["s2"], data["s3"], data["name"]
        )
        
        # ============================================================
        # GUARDAR DOCUMENTO ANTES DE SUBIR
        # ============================================================
        try:
            if doc and doc.FileName:
                doc.recompute()
                if FreeCADGui:
                    # Guardado real, idéntico a darle click al botón de guardar
                    FreeCADGui.runCommand("Std_Save", 0)
                else:
                    # Modo sin interfaz (testing / headless)
                    doc.save()

        except Exception as e:
            FreeCAD.Console.PrintError(f"No se pudo guardar antes de subir: {e}\n")

        # --------------------------------------------------------
        # Subir SIEMPRE, aunque ya existía (reemplazo permitido)
        # --------------------------------------------------------
        metadata = {
            "x-amz-meta-revision": str(data["revision"]),
            "x-amz-meta-descripcion": data["descripcion"],
            "x-amz-meta-comment": data["comment"]
        }
        
        etag = upload_file(doc.FileName, object_name, metadata, BUCKET_MODEL)

        if etag:
            try:
                # Actualizar atributos en el documento FreeCAD
                doc.Base_etag = etag
                doc.Base_revision = str(data["revision"])
                doc.Base_descripcion = data["descripcion"]
                doc.Base_comment = data["comment"]

                doc.recompute()
                doc.save()

            except Exception as e:
                FreeCAD.Console.PrintError(f"Error guardando metadatos: {e}\n")

            show_popup(
                "Completado",
                f"Proyecto subido:\n{object_name}\nETag: {etag}"
            )

    def IsActive(self):
        return True


# ============================================================
# ADD ATTRIBUTES TO CURRENT PROJECT
# ============================================================

class AddAttributesCMD:

    def GetResources(self):
        icon = os.path.join(os.path.dirname(__file__), "Resources/Icons/dProp.svg") \
               if os.path.exists(os.path.join(os.path.dirname(__file__), "Resources/Icons/dProp.svg")) \
               else ""

        return {
            "Pixmap": icon,
            "MenuText": "Configurar Documento",
            "ToolTip": "Crea las propiedades necesarias para el archivo."
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        if not doc:
            show_popup("Error", "No hay documento activo.")
            return

        # Lista de propiedades esperadas
        required = {
            "Base_comment": "",
            "Base_etag": "",
            "Base_revision": "1.00",
            "Base_descripcion": ""
        }

        already = []
        created = []

        # Crear propiedades si no existen
        for prop, default_value in required.items():
            if hasattr(doc, prop):
                already.append(prop)
            else:
                try:
                    doc.addProperty(
                        "App::PropertyString",
                        prop,
                        "Texmex Metadata",
                        f"Propiedad automática: {prop}"
                    )
                    setattr(doc, prop, default_value)
                    created.append(prop)
                except Exception as e:
                    FreeCAD.Console.PrintError(f"Error creando {prop}: {e}\n")

        # Guardar cambios
        try:
            doc.recompute()
            doc.save()
        except Exception as e:
            FreeCAD.Console.PrintError(f"Error guardando el documento: {e}\n")

        # Mostrar resultados
        if created:
            show_popup(
                "Atributos creados",
                "Se agregaron las siguientes propiedades:\n" +
                "\n".join(f"• {p}" for p in created)
            )

        if already:
            show_popup(
                "Atributos existentes",
                "Estas propiedades ya existían:\n" +
                "\n".join(f"• {p}" for p in already)
            )

    def IsActive(self):
        return True
