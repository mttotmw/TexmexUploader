# ============================================================
# library.py → Librería de modelos Texmex (MinIO)
# ============================================================

import os
import FreeCAD

try:
    import FreeCADGui
except ImportError:
    FreeCADGui = None

# Qt
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

# Utilidades comunes
from common import (
    Minio, ENDPOINT, ACCESS_KEY, SECRET_KEY,
    BUCKET_MODEL,
    list_subfolders, _slug, _pretty, show_popup
)

# Helper de preview
from modelviewer import generate_preview_for_object

# Import helpers
from modelimporter import (
    download_model_to_temp,
    open_model_as_new,
    import_model_into_current,
    delete_model_from_bucket
)

DOCK_OBJECT_NAME = "TexmexModelLibraryDock"


# ============================================================
#  WIDGET PRINCIPAL
# ============================================================

class TexmexModelLibraryWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.client = Minio(
            ENDPOINT,
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY,
            secure=False
        )

        self.current_prefix = ""
        self.current_key = None
        self.loaded_prefixes = set()

        self._build_ui()
        self._load_root_areas()


    # ----------------------------------------------------------
    # UI
    # ----------------------------------------------------------
    def _build_ui(self):
        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(4, 4, 4, 4)

        # Titulo
        title = QtWidgets.QLabel("<b>Librería de Modelos Texmex</b>")
        title.setAlignment(QtCore.Qt.AlignCenter)
        main.addWidget(title)

        # FallBack Refresh Button (in-widget)
        top_bar = QtWidgets.QHBoxLayout()
        top_bar.addStretch(1)

        self.btn_refresh = QtWidgets.QToolButton()
        icon_sync = QtGui.QIcon(os.path.join(os.path.dirname(__file__), "Resources/Icons/sync.svg"))
        self.btn_refresh.setIcon(icon_sync)
        self.btn_refresh.setToolTip("Refrescar áreas y archivos")
        self.btn_refresh.clicked.connect(self._load_root_areas)

        top_bar.addWidget(self.btn_refresh)
        main.addLayout(top_bar)

        # Ruta
        self.path_label = QtWidgets.QLabel("Ruta: /")
        self.path_label.setStyleSheet("color: gray;")
        main.addWidget(self.path_label)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main.addWidget(splitter, 1)

        # ------------------------------------------------------
        # Árbol
        # ------------------------------------------------------
        left = QtWidgets.QWidget()
        ll = QtWidgets.QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(260)
        ll.addWidget(self.tree)

        splitter.addWidget(left)

        # ------------------------------------------------------
        # Panel derecho
        # ------------------------------------------------------
        right = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        rl.addWidget(QtWidgets.QLabel("Archivos en carpeta:"))
        self.file_list = QtWidgets.QListWidget()
        self.file_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        rl.addWidget(self.file_list, 1)

        rl.addWidget(QtWidgets.QLabel("Vista previa:"))
        self.preview_label = QtWidgets.QLabel()
        self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setFrameShape(QtWidgets.QFrame.StyledPanel)
        rl.addWidget(self.preview_label, 1)

        # Botones
        bar = QtWidgets.QHBoxLayout()
        self.btn_open_new = QtWidgets.QPushButton("Abrir")
        self.btn_import = QtWidgets.QPushButton("Importar")
        self.btn_delete = QtWidgets.QPushButton("Eliminar")

        bar.addWidget(self.btn_open_new)
        bar.addWidget(self.btn_import)
        bar.addWidget(self.btn_delete)

        rl.addLayout(bar)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        # ------------------------------------------------------
        # SIGNALS
        # ------------------------------------------------------
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.currentItemChanged.connect(self._on_tree_selection_changed)
        self.file_list.currentItemChanged.connect(self._on_file_selection_changed)

        self.btn_open_new.clicked.connect(self._on_open_new_clicked)
        self.btn_import.clicked.connect(self._on_import_clicked)
        self.btn_delete.clicked.connect(self._on_delete_clicked)


    # ============================================================
    # CARGAR ÁREAS
    # ============================================================
    def _load_root_areas(self):

        self.tree.blockSignals(True)
        self.tree.clear()
        self.loaded_prefixes.clear()
        self.tree.blockSignals(False)

        root = QtWidgets.QTreeWidgetItem(self.tree, ["Áreas"])
        root.setData(0, QtCore.Qt.UserRole, "")
        root.setData(0, QtCore.Qt.UserRole + 1, True)
        root.setExpanded(True)

        areas = list_subfolders(BUCKET_MODEL, "")
        for area in areas:
            area_slug = _slug(area)
            item = QtWidgets.QTreeWidgetItem(root, [area])
            item.setData(0, QtCore.Qt.UserRole, area_slug)
            item.setData(0, QtCore.Qt.UserRole + 1, False)

        self.tree.setCurrentItem(root)
        self._load_files_for_prefix("")


    # ============================================================
    # SUBCARPETAS
    # ============================================================
    def _ensure_children_loaded(self, item):

        loaded = item.data(0, QtCore.Qt.UserRole + 1)
        if loaded:
            return

        prefix = item.data(0, QtCore.Qt.UserRole) or ""

        if prefix in self.loaded_prefixes:
            item.setData(0, QtCore.Qt.UserRole + 1, True)
            return

        subs = list_subfolders(BUCKET_MODEL, prefix)

        for sub in subs:
            sub_slug = _slug(sub)
            full_prefix = f"{prefix}/{sub_slug}" if prefix else sub_slug

            child = QtWidgets.QTreeWidgetItem(item, [sub])
            child.setData(0, QtCore.Qt.UserRole, full_prefix)
            child.setData(0, QtCore.Qt.UserRole + 1, False)

        self.loaded_prefixes.add(prefix)
        item.setData(0, QtCore.Qt.UserRole + 1, True)


    def _on_item_expanded(self, item):
        try:
            self._ensure_children_loaded(item)
        except Exception as e:
            FreeCAD.Console.PrintError(f"Error expandiendo carpeta: {e}\n")


    # ============================================================
    # SELECCIÓN DE CARPETA
    # ============================================================
    def _on_tree_selection_changed(self, current, previous):
        if not current:
            return

        prefix = current.data(0, QtCore.Qt.UserRole) or ""

        self.current_prefix = prefix
        self.path_label.setText(f"Ruta: /{prefix}" if prefix else "Ruta: /")

        self._ensure_children_loaded(current)
        self._load_files_for_prefix(prefix)


    # ============================================================
    # ARCHIVOS EN CARPETA
    # ============================================================
    def _load_files_for_prefix(self, prefix):

        self.file_list.clear()
        self.preview_label.clear()
        self.current_key = None

        base = prefix.strip("/")
        base = base + "/" if base else ""

        try:
            objects = self.client.list_objects(
                BUCKET_MODEL,
                prefix=base,
                recursive=False
            )
            for obj in objects:
                key = obj.object_name

                name_part = key[len(base):]

                if "/" in name_part:
                    continue

                if not name_part.lower().endswith(".fcstd"):
                    continue

                item = QtWidgets.QListWidgetItem(name_part)
                item.setData(QtCore.Qt.UserRole, base + name_part)
                self.file_list.addItem(item)

        except Exception as e:
            FreeCAD.Console.PrintError(f"Error listando objetos: {e}\n")
            show_popup("Error", f"No se pudieron listar modelos:\n{e}")


    # ============================================================
    # SELECCIÓN DE ARCHIVO
    # ============================================================
    def _on_file_selection_changed(self, current, previous):

        if not current:
            self.current_key = None
            self.preview_label.clear()
            return

        key = current.data(QtCore.Qt.UserRole)
        self.current_key = key

        png = generate_preview_for_object(BUCKET_MODEL, key)

        if png and os.path.exists(png):
            pix = QtGui.QPixmap(png)
            self.preview_label.setPixmap(
                pix.scaled(
                    self.preview_label.width(),
                    self.preview_label.height(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
            )
        else:
            self.preview_label.setText("Sin vista previa disponible.")


    # ============================================================
    # BOTONES
    # ============================================================
    def _on_open_new_clicked(self):
        if not self.current_key:
            show_popup("Atención", "Selecciona un archivo primero.")
            return
        open_model_as_new(BUCKET_MODEL, self.current_key)

    def _on_import_clicked(self):
        if not self.current_key:
            show_popup("Atención", "Selecciona un archivo primero.")
            return
        import_model_into_current(BUCKET_MODEL, self.current_key)

    def _on_delete_clicked(self):
        if not self.current_key:
            show_popup("Atención", "Selecciona un archivo primero.")
            return

        confirm = QtWidgets.QMessageBox.question(
            self,
            "Eliminar",
            f"¿Eliminar este modelo?\n\n{self.current_key}",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        if delete_model_from_bucket(BUCKET_MODEL, self.current_key):
            self._load_files_for_prefix(self.current_prefix)
            self.preview_label.clear()
            self.current_key = None


# ============================================================
# COMMAND: DOCK
# ============================================================

class OpenTexmexLibraryCmd:

    def GetResources(self):
        icon = os.path.join(os.path.dirname(__file__), "Resources/Icons/cloud.svg")
        return {
            "Pixmap": icon,
            "MenuText": "Librería de Modelos",
            "ToolTip": "Abrir librería Texmex desde MinIO"
        }

    def Activated(self):
        if not FreeCADGui:
            show_popup("Error", "La interfaz gráfica no está disponible.")
            return

        mw = FreeCADGui.getMainWindow()

        existing = mw.findChild(QtWidgets.QDockWidget, DOCK_OBJECT_NAME)
        if existing:
            existing.show()
            existing.raise_()
            return

        dock = QtWidgets.QDockWidget("Librería de Modelos Texmex", mw)
        dock.setObjectName(DOCK_OBJECT_NAME)
        dock.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)

        widget = TexmexModelLibraryWidget(dock)
        dock.setWidget(widget)

        # ----------------------------------------------------------
        # CUSTOM TITLE BAR WITH REFRESH BUTTON
        # ----------------------------------------------------------
        try:
            tb = QtWidgets.QWidget()
            tbl = QtWidgets.QHBoxLayout(tb)
            tbl.setContentsMargins(5, 2, 5, 2)

            lbl = QtWidgets.QLabel("Librería de Modelos Texmex")
            lbl.setStyleSheet("font-weight:bold;")

            refresh_btn = QtWidgets.QToolButton()
            icon_sync = QtGui.QIcon(os.path.join(os.path.dirname(__file__), "Resources/Icons/sync.svg"))
            refresh_btn.setIcon(icon_sync)
            refresh_btn.setToolTip("Refrescar librería")
            refresh_btn.clicked.connect(widget._load_root_areas)

            tbl.addWidget(lbl, 1)
            tbl.addWidget(refresh_btn, 0)
            tb.setLayout(tbl)

            dock.setTitleBarWidget(tb)

        except Exception as e:
            FreeCAD.Console.PrintError(f"No se pudo customizar title bar: {e}\n")

        mw.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        dock.resize(500, 600)
        dock.show()

    def IsActive(self):
        return True
