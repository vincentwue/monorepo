from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from .copy_metrics import CopyMetricsMixin
from .prompt_panel import PromptPanelMixin
from .workspace import WorkspaceMixin


class ContextProviderWindow(PromptPanelMixin, CopyMetricsMixin, WorkspaceMixin, QtWidgets.QMainWindow):
    """Main application window composed of distinct feature mixins."""

    def __init__(self) -> None:
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowTitle("Context Provider")
        self.resize(1440, 900)

        self._init_workspace_state()
        self._init_prompt_panel_state()

        self._build_ui()
        self.restore_layout()
        QtCore.QTimer.singleShot(250, self._startup_load)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        icon_path = Path(__file__).with_name("assets").joinpath("app_icon.png")
        if icon_path.exists():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))

        self._build_central_splitters()
        self.scope_dock = self._create_scope_dock()
        self.filter_dock = self._create_filter_dock()
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.scope_dock)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.filter_dock)
        self.tabifyDockWidget(self.scope_dock, self.filter_dock)
        self.scope_dock.raise_()
        self._build_view_menu()
        self.statusBar().showMessage("Choose a folder to load context.")
        self._update_copy_line_metrics()

    def _build_view_menu(self) -> None:
        view_menu = self.menuBar().addMenu("&View")
        if self.scope_dock:
            view_menu.addAction(self.scope_dock.toggleViewAction())
        if self.filter_dock:
            view_menu.addAction(self.filter_dock.toggleViewAction())

    def expand_tree(self) -> None:
        if self.tree_widget:
            self.tree_widget.expandAll()

    def collapse_tree(self) -> None:
        if self.tree_widget:
            self.tree_widget.collapseAll()

    def _build_central_splitters(self) -> None:
        self.tree_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.tree_splitter.setChildrenCollapsible(False)
        self.tree_splitter.addWidget(self._build_tree_panel())
        self.tree_splitter.addWidget(self._build_table_panel())
        self.tree_splitter.setStretchFactor(0, 3)
        self.tree_splitter.setStretchFactor(1, 2)

        self.preview_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.preview_splitter.setChildrenCollapsible(False)
        self.preview_splitter.addWidget(self._build_ascii_panel())
        self.preview_splitter.addWidget(self._build_preview_panel())
        self.preview_splitter.setStretchFactor(0, 1)
        self.preview_splitter.setStretchFactor(1, 1)

        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.tree_splitter)
        self.main_splitter.addWidget(self.preview_splitter)
        self.main_splitter.addWidget(self._build_prompt_panel())
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setStretchFactor(2, 2)
        self.setCentralWidget(self.main_splitter)
