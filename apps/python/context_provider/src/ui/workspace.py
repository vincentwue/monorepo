from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from copy_actions import copy_context, copy_selected, copy_signatures
from file_tree import build_ascii_from_paths, build_ascii_tree_text, gather_tree_entries
from filters import apply_filters
from ignore_patterns import IGNORE_PATTERNS
from utils import log


class WorkspaceMixin:
    TREE_PATH_ROLE = QtCore.Qt.UserRole
    TREE_IS_DIR_ROLE = QtCore.Qt.UserRole + 1
    FILTER_DELAY_MS = 400

    def _init_workspace_state(self) -> None:
        self.settings = QtCore.QSettings()
        self._maybe_migrate_legacy_config()
        self.clipboard = QtGui.QGuiApplication.clipboard()
        self.default_ignore_patterns = list(IGNORE_PATTERNS)
        self.current_folder = self._sanitize_path(self.settings.value("scope/lastFolder", "", str))
        self.selected_paths = set(self._read_list_setting("selection/paths"))
        self.filter_selected_paths: set[str] = set()
        self.visible_filter_paths: set[str] = set()
        self.context_candidate_files: set[str] = set()
        self.parent_lookup: dict[str, Optional[str]] = {}
        self.tree_items: dict[str, QtWidgets.QTreeWidgetItem] = {}
        self.all_paths: list[str] = []
        self.file_paths: list[str] = []
        self.file_cache: dict[str, str] = {}
        self.line_count_cache: dict[str, int] = {}
        self.signature_preview_cache: dict[str, list[str]] = {}
        self.current_table_paths: list[str] = []
        self._suppress_tree_signal = False
        self.filter_timer = QtCore.QTimer(self)
        self.filter_timer.setSingleShot(True)
        self.filter_timer.timeout.connect(self.apply_filters)

        self.path_edit: Optional[QtWidgets.QLineEdit] = None
        self.ignore_editor: Optional[QtWidgets.QPlainTextEdit] = None
        self.include_editor: Optional[QtWidgets.QPlainTextEdit] = None
        self.path_filter_editor: Optional[QtWidgets.QPlainTextEdit] = None
        self.tree_widget: Optional[QtWidgets.QTreeWidget] = None
        self.path_table: Optional[QtWidgets.QTableWidget] = None
        self.ascii_view: Optional[QtWidgets.QPlainTextEdit] = None
        self.preview_view: Optional[QtWidgets.QPlainTextEdit] = None
        self.preview_stats_label: Optional[QtWidgets.QLabel] = None
        self.scope_dock: Optional[QtWidgets.QDockWidget] = None
        self.filter_dock: Optional[QtWidgets.QDockWidget] = None
        self.copy_line_labels: dict[str, QtWidgets.QLabel] = {}

    def _build_tree_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(QtWidgets.QLabel("Directory Tree Explorer"))

        buttons = QtWidgets.QHBoxLayout()
        expand_btn = QtWidgets.QPushButton("Expand All")
        expand_btn.clicked.connect(self.expand_tree)
        collapse_btn = QtWidgets.QPushButton("Collapse All")
        collapse_btn.clicked.connect(self.collapse_tree)
        buttons.addWidget(expand_btn)
        buttons.addWidget(collapse_btn)
        layout.addLayout(buttons)

        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.itemChanged.connect(self._handle_tree_item_changed)
        layout.addWidget(self.tree_widget, 1)
        return panel

    def _build_table_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(QtWidgets.QLabel("Path Selection Table"))

        buttons = QtWidgets.QHBoxLayout()
        for text, handler in (
            ("Select All", self.select_all),
            ("Deselect All", self.deselect_all),
            ("Select Visible", self.select_search_results),
            ("Use Filter Selection", self.select_filter_results),
        ):
            btn = QtWidgets.QPushButton(text)
            btn.clicked.connect(handler)
            buttons.addWidget(btn)
        layout.addLayout(buttons)

        self.path_table = QtWidgets.QTableWidget(0, 5)
        self.path_table.setHorizontalHeaderLabels(["Filter", "Output", "#", "Relative Path", "Lines"])
        self.path_table.setAlternatingRowColors(True)
        self.path_table.verticalHeader().setVisible(False)
        header = self.path_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        header.sectionResized.connect(self._persist_table_columns)
        self._restore_table_columns()
        self.path_table.cellClicked.connect(self.handle_path_table_click)
        self.path_table.cellDoubleClicked.connect(self._handle_table_double_click)
        layout.addWidget(self.path_table, 1)
        return panel

    def _build_ascii_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(QtWidgets.QLabel("Project Tree Overview"))
        self.ascii_view = QtWidgets.QPlainTextEdit()
        self.ascii_view.setReadOnly(True)
        self.ascii_view.setFont(self._monospace_font())
        layout.addWidget(self.ascii_view, 1)
        return panel

    def _build_preview_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(QtWidgets.QLabel("Preview Output"))
        stats_label = QtWidgets.QLabel("Selected 0/0 | Visible 0 | Filter 0 | Context 0")
        stats_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        stats_label.setObjectName("previewStatsLabel")
        layout.addWidget(stats_label)
        self.preview_stats_label = stats_label

        buttons_column = QtWidgets.QVBoxLayout()
        buttons_column.setSpacing(6)
        button_specs = [
            ("selected", "Copy Selected", lambda: copy_selected(self)),
            ("context", "Copy Context", lambda: copy_context(self)),
            ("signatures", "Copy Signatures", lambda: copy_signatures(self)),
        ]
        for key, text, handler in button_specs:
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(6)
            btn = QtWidgets.QPushButton(text)
            btn.clicked.connect(handler)
            label = QtWidgets.QLabel("0 lines")
            label.setMinimumWidth(80)
            label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            row.addWidget(btn, 1)
            row.addWidget(label, 0)
            buttons_column.addLayout(row)
            self.copy_line_labels[key] = label
        layout.addLayout(buttons_column)

        self.preview_view = QtWidgets.QPlainTextEdit()
        self.preview_view.setReadOnly(True)
        self.preview_view.setFont(self._monospace_font())
        layout.addWidget(self.preview_view, 1)
        return panel

    def _create_scope_dock(self) -> QtWidgets.QDockWidget:
        dock = QtWidgets.QDockWidget("Scope", self)
        dock.setObjectName("ScopeDock")
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(QtWidgets.QLabel("Base Folder"))
        path_row = QtWidgets.QHBoxLayout()
        self.path_edit = QtWidgets.QLineEdit(self.current_folder)
        self.path_edit.editingFinished.connect(self._handle_path_edit_finished)
        path_row.addWidget(self.path_edit, 1)
        choose_btn = QtWidgets.QPushButton("Choose")
        choose_btn.clicked.connect(self.choose_folder)
        path_row.addWidget(choose_btn)
        load_btn = QtWidgets.QPushButton("Load")
        load_btn.clicked.connect(self.load_content)
        path_row.addWidget(load_btn)
        layout.addLayout(path_row)

        layout.addWidget(QtWidgets.QLabel("Ignore Patterns"))
        self.ignore_editor = QtWidgets.QPlainTextEdit()
        self.ignore_editor.setFont(self._monospace_font())
        self.ignore_editor.setPlainText("\n".join(self._initial_ignore_patterns()))
        layout.addWidget(self.ignore_editor, 1)

        button_row = QtWidgets.QHBoxLayout()
        apply_btn = QtWidgets.QPushButton("Apply & Refresh")
        apply_btn.clicked.connect(self.apply_ignore_patterns)
        reset_btn = QtWidgets.QPushButton("Reset Defaults")
        reset_btn.clicked.connect(self.reset_ignore_patterns)
        button_row.addWidget(apply_btn)
        button_row.addWidget(reset_btn)
        layout.addLayout(button_row)
        layout.addWidget(QtWidgets.QLabel("One pattern per line (substring match)."))

        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        return dock

    def _create_filter_dock(self) -> QtWidgets.QDockWidget:
        dock = QtWidgets.QDockWidget("Filters", self)
        dock.setObjectName("FiltersDock")
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(QtWidgets.QLabel("In-File Includes (one per line)"))
        self.include_editor = QtWidgets.QPlainTextEdit()
        self.include_editor.setFont(self._monospace_font())
        self.include_editor.setPlainText("\n".join(self._read_list_setting("filters/infile")))
        self.include_editor.textChanged.connect(self._handle_include_text_changed)
        layout.addWidget(self.include_editor, 1)
        include_buttons = QtWidgets.QHBoxLayout()
        include_apply = QtWidgets.QPushButton("Apply")
        include_apply.clicked.connect(self.apply_filters)
        include_clear = QtWidgets.QPushButton("Clear")
        include_clear.clicked.connect(self.clear_infile_filters)
        include_buttons.addWidget(include_apply)
        include_buttons.addWidget(include_clear)
        layout.addLayout(include_buttons)

        layout.addWidget(QtWidgets.QLabel("Path Filters (one per line)"))
        self.path_filter_editor = QtWidgets.QPlainTextEdit()
        self.path_filter_editor.setFont(self._monospace_font())
        self.path_filter_editor.setPlainText("\n".join(self._read_list_setting("filters/path")))
        self.path_filter_editor.textChanged.connect(self._handle_path_filter_text_changed)
        layout.addWidget(self.path_filter_editor, 1)
        path_buttons = QtWidgets.QHBoxLayout()
        path_apply = QtWidgets.QPushButton("Apply")
        path_apply.clicked.connect(self.apply_filters)
        path_clear = QtWidgets.QPushButton("Clear")
        path_clear.clicked.connect(self.clear_path_filters)
        path_buttons.addWidget(path_apply)
        path_buttons.addWidget(path_clear)
        layout.addLayout(path_buttons)

        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        return dock

    def _monospace_font(self) -> QtGui.QFont:
        font = QtGui.QFont("Consolas")
        font.setStyleHint(QtGui.QFont.Monospace)
        return font

    def restore_layout(self) -> None:
        geometry = self.settings.value("mainGeometry")
        if isinstance(geometry, QtCore.QByteArray):
            self.restoreGeometry(geometry)
        state = self.settings.value("mainState")
        if isinstance(state, QtCore.QByteArray):
            self.restoreState(state)
        for key, splitter in (
            ("splitter/main", getattr(self, "main_splitter", None)),
            ("splitter/tree", getattr(self, "tree_splitter", None)),
            ("splitter/preview", getattr(self, "preview_splitter", None)),
        ):
            if splitter is None:
                continue
            value = self.settings.value(key)
            if isinstance(value, QtCore.QByteArray):
                splitter.restoreState(value)

    def save_layout(self) -> None:
        self.settings.setValue("mainGeometry", self.saveGeometry())
        self.settings.setValue("mainState", self.saveState())
        if hasattr(self, "main_splitter"):
            self.settings.setValue("splitter/main", self.main_splitter.saveState())
        if hasattr(self, "tree_splitter"):
            self.settings.setValue("splitter/tree", self.tree_splitter.saveState())
        if hasattr(self, "preview_splitter"):
            self.settings.setValue("splitter/preview", self.preview_splitter.saveState())
        self.settings.sync()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[override]
        self.save_layout()
        super().closeEvent(event)

    def _persist_table_columns(self) -> None:
        if not self.path_table:
            return
        header = self.path_table.horizontalHeader()
        widths = [header.sectionSize(idx) for idx in range(header.count())]
        self.settings.setValue("table/widths", widths)

    def _restore_table_columns(self) -> None:
        widths = self.settings.value("table/widths")
        if not widths or not isinstance(widths, (list, tuple)):
            return
        for idx, width in enumerate(widths):
            try:
                self.path_table.setColumnWidth(idx, int(width))  # type: ignore[arg-type]
            except (ValueError, TypeError, AttributeError):
                continue

    def show_info(self, msg: str, duration: int = 3) -> None:
        log(f"INFO: {msg}")
        self.statusBar().showMessage(msg, duration * 1000)

    def choose_folder(self) -> None:
        start_dir = self.current_folder or str(Path.home())
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder", start_dir)
        if not folder:
            return
        self.current_folder = self._sanitize_path(folder)
        if self.path_edit:
            self.path_edit.setText(self.current_folder)
        self._persist_last_folder()
        self.show_info("Folder selected. Click 'Load' to refresh.", duration=3)

    def _handle_path_edit_finished(self) -> None:
        if not self.path_edit:
            return
        folder = self._sanitize_path(self.path_edit.text().strip())
        if folder == self.current_folder:
            return
        self.current_folder = folder
        self._persist_last_folder()
        self.show_info("Folder updated. Click 'Load' to rebuild context.", duration=3)

    def load_content(self) -> None:
        if not self.current_folder:
            self.show_info("Please choose a folder first.", duration=3)
            return
        self._persist_last_folder()
        self.refresh_tree()

    def refresh_tree(self, patterns: list[str] | None = None) -> None:
        folder = self.current_folder
        if not folder or not os.path.isdir(folder):
            self.show_info("Selected folder is not available.", duration=3)
            return
        if patterns is None:
            patterns = self.get_ignore_patterns()
        entries = gather_tree_entries(folder, patterns)
        self.parent_lookup = {folder: None}
        self.tree_items.clear()
        self.all_paths = [entry.path for entry in entries]
        self.file_paths = [entry.path for entry in entries if not entry.is_dir]
        valid_selection = set(path for path in self.selected_paths if path in self.all_paths)
        if valid_selection != self.selected_paths:
            self.selected_paths = valid_selection
            self._persist_selected_paths()
        self.visible_filter_paths = set(self.all_paths)
        self.filter_selected_paths.clear()

        if not self.tree_widget:
            return

        self.tree_widget.blockSignals(True)
        self.tree_widget.clear()
        root_label = os.path.basename(folder) or folder
        root_item = QtWidgets.QTreeWidgetItem([root_label])
        root_item.setData(0, self.TREE_PATH_ROLE, folder)
        root_item.setData(0, self.TREE_IS_DIR_ROLE, True)
        root_item.setFlags(root_item.flags() & ~QtCore.Qt.ItemIsUserCheckable)
        self.tree_widget.addTopLevelItem(root_item)
        self.tree_items[folder] = root_item

        style = self.style()
        dir_icon = style.standardIcon(QtWidgets.QStyle.SP_DirIcon)
        file_icon = style.standardIcon(QtWidgets.QStyle.SP_FileIcon)

        for entry in entries:
            parent_path = entry.parent or folder
            parent_item = self.tree_items.get(parent_path, root_item)
            item = QtWidgets.QTreeWidgetItem(parent_item, [entry.name])
            item.setData(0, self.TREE_PATH_ROLE, entry.path)
            item.setData(0, self.TREE_IS_DIR_ROLE, entry.is_dir)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            icon = dir_icon if entry.is_dir else file_icon
            item.setIcon(0, icon)
            item.setCheckState(0, QtCore.Qt.Checked if entry.path in self.selected_paths else QtCore.Qt.Unchecked)
            self.tree_items[entry.path] = item
            self.parent_lookup[entry.path] = parent_path

        self.tree_widget.expandAll()
        self.tree_widget.blockSignals(False)
        self.update_path_table(self.all_paths)
        self._update_ascii_overview()
        self.show_info(f"Context refreshed with {len(entries)} entries.", duration=2)
        self._update_copy_line_metrics()

    def get_ignore_patterns(self) -> list[str]:
        if not self.ignore_editor:
            return self.default_ignore_patterns
        lines = self.ignore_editor.toPlainText().splitlines()
        patterns = [line.strip() for line in lines if line.strip()]
        return patterns or self.default_ignore_patterns

    def apply_ignore_patterns(self) -> None:
        patterns = self.get_ignore_patterns()
        self.settings.setValue("scope/ignorePatterns", patterns)
        self.refresh_tree(patterns)

    def reset_ignore_patterns(self) -> None:
        if self.ignore_editor:
            self.ignore_editor.setPlainText("\n".join(self.default_ignore_patterns))
        self.apply_ignore_patterns()

    def get_path_filter_terms(self) -> list[str]:
        if not self.path_filter_editor:
            return []
        lines = self.path_filter_editor.toPlainText().splitlines()
        return [line.strip().lower() for line in lines if line.strip()]

    def get_infile_filter_terms(self) -> list[str]:
        if not self.include_editor:
            return []
        lines = self.include_editor.toPlainText().splitlines()
        return [line.strip().lower() for line in lines if line.strip()]

    def clear_path_filters(self) -> None:
        if self.path_filter_editor:
            self.path_filter_editor.clear()
        self.apply_filters()

    def clear_infile_filters(self) -> None:
        if self.include_editor:
            self.include_editor.clear()
        self.apply_filters()

    def schedule_content_filter(self) -> None:
        if self.filter_timer.isActive():
            self.filter_timer.stop()
        self.filter_timer.start(self.FILTER_DELAY_MS)
        self._persist_filter_inputs()

    def _handle_include_text_changed(self) -> None:
        self.schedule_content_filter()

    def _handle_path_filter_text_changed(self) -> None:
        self.schedule_content_filter()

    def _persist_filter_inputs(self) -> None:
        if self.include_editor:
            includes = [
                line.strip()
                for line in self.include_editor.toPlainText().splitlines()
                if line.strip()
            ]
            if includes:
                self.settings.setValue("filters/infile", includes)
            else:
                self.settings.remove("filters/infile")
        if self.path_filter_editor:
            paths = [
                line.strip()
                for line in self.path_filter_editor.toPlainText().splitlines()
                if line.strip()
            ]
            if paths:
                self.settings.setValue("filters/path", paths)
            else:
                self.settings.remove("filters/path")

    def apply_filters(self) -> None:
        if not self.all_paths:
            return
        path_terms = self.get_path_filter_terms()
        file_terms = self.get_infile_filter_terms()
        if not path_terms and not file_terms:
            self.filter_selected_paths.clear()
            self.visible_filter_paths = set(self.all_paths)
            self.context_candidate_files = set()
            self._update_tree_visibility(set(self.all_paths), filters_active=False)
            self.update_path_table(self.all_paths)
            self._update_ascii_overview()
            self._update_copy_line_metrics()
            return

        result = apply_filters(
            self.all_paths,
            self.file_paths,
            path_terms,
            file_terms,
            self.parent_lookup,
            self.file_cache,
        )
        self.filter_selected_paths = set(result.matched_paths)
        self.visible_filter_paths = set(result.visible_paths)
        self.context_candidate_files = set(result.matched_files)
        self._update_tree_visibility(result.matched_paths, filters_active=True)
        target_paths = result.visible_paths or self.all_paths
        self.update_path_table(target_paths)
        if target_paths:
            ascii_output = build_ascii_from_paths(self.current_folder or "", target_paths)
            if self.ascii_view:
                self.ascii_view.setPlainText(ascii_output)
        else:
            if self.ascii_view:
                self.ascii_view.setPlainText("(no results)")
        self.show_info("Filter applied.", duration=2)
        self._update_copy_line_metrics()

    def _update_tree_visibility(self, matched_paths: set[str], filters_active: bool) -> None:
        for path, item in self.tree_items.items():
            if path == self.current_folder:
                item.setHidden(False)
                continue
            hidden = filters_active and path not in matched_paths
            item.setHidden(hidden)

    def select_all(self) -> None:
        target = self.current_table_paths or self.all_paths
        self.selected_paths = set(target)
        self._persist_selected_paths()
        self.update_path_table(target)
        self.sync_tree_checkboxes()
        self.show_info(f"Selected all {len(self.selected_paths)} items.")
        self._update_copy_line_metrics()

    def deselect_all(self) -> None:
        self.selected_paths.clear()
        self._persist_selected_paths()
        self.update_path_table(self.current_table_paths or self.all_paths)
        self.sync_tree_checkboxes()
        self.show_info("Deselected all items.")
        self._update_copy_line_metrics()

    def select_search_results(self) -> None:
        targets = self.visible_filter_paths or set(self.all_paths)
        self.selected_paths.update(targets)
        self._persist_selected_paths()
        self.update_path_table(self.current_table_paths or self.all_paths)
        self.sync_tree_checkboxes()
        self.show_info(f"Selected {len(targets)} visible paths.")
        self._update_copy_line_metrics()

    def select_filter_results(self) -> None:
        targets = self.visible_filter_paths or self.filter_selected_paths
        if not targets:
            self.show_info("No filtered paths to select.", duration=2)
            return
        self.selected_paths = set(targets)
        self._persist_selected_paths()
        self.update_path_table(self.current_table_paths or self.all_paths)
        self.sync_tree_checkboxes()
        self.show_info(f"Selected {len(targets)} filtered paths.")
        self._update_copy_line_metrics()

    def set_clipboard_text(self, text: str) -> None:
        self.clipboard.setText(text)

    def update_result_preview(self, text: str, title: str | None = None) -> None:
        if not self.preview_view:
            return
        body = text or "(no data)"
        if title:
            header = f"{title}\n{'-' * len(title)}\n\n"
        else:
            header = ""
        self.preview_view.setPlainText(header + body)

    def _update_preview_stats(self) -> None:
        if not self.preview_stats_label:
            return
        total = len(self.all_paths)
        selected = len(self.selected_paths)
        visible = len(self.current_table_paths or self.all_paths)
        filter_hits = len(self.filter_selected_paths) if self.filter_selected_paths else 0
        context_hits = len(self.context_candidate_files)
        text = (
            f"Selected {selected}/{total} | "
            f"Visible {visible} | Filter {filter_hits} | Context {context_hits}"
        )
        self.preview_stats_label.setText(text)

    def _handle_tree_item_changed(self, item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        if self._suppress_tree_signal or column != 0:
            return
        path = item.data(0, self.TREE_PATH_ROLE)
        if not isinstance(path, str):
            return
        checked = item.checkState(0) == QtCore.Qt.Checked
        is_dir = bool(item.data(0, self.TREE_IS_DIR_ROLE))
        affected_paths = [path]
        if is_dir:
            self._suppress_tree_signal = True
            try:
                self._set_subtree_checkstate(item, QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
            finally:
                self._suppress_tree_signal = False
            affected_paths.extend(self._collect_descendant_paths(item))

        if checked:
            self.selected_paths.update(affected_paths)
        else:
            for target in affected_paths:
                self.selected_paths.discard(target)
        self._persist_selected_paths()
        self.update_path_table(self.current_table_paths or self.all_paths)
        self._update_copy_line_metrics()

    def handle_path_table_click(self, row: int, column: int) -> None:
        if column != 1 or not self.path_table:
            return
        path_item = self.path_table.item(row, 3)
        if not path_item:
            return
        path = path_item.data(QtCore.Qt.UserRole)
        if isinstance(path, str):
            self.toggle_path_selection(path)

    def toggle_path_selection(self, path: str) -> None:
        if path in self.selected_paths:
            self.selected_paths.remove(path)
        else:
            self.selected_paths.add(path)
        self._persist_selected_paths()
        self.update_path_table(self.current_table_paths or self.all_paths)
        self.sync_tree_checkboxes()
        self._update_copy_line_metrics()

    def _handle_table_double_click(self, row: int, column: int) -> None:
        self.open_path_from_table(row)

    def open_path_from_table(self, row: int) -> None:
        if not self.path_table:
            return
        path_item = self.path_table.item(row, 3)
        if not path_item:
            return
        path = path_item.data(QtCore.Qt.UserRole)
        if not isinstance(path, str):
            return
        self._open_path(path)

    def _open_path(self, path: str) -> None:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            self.show_info("Selected path does not exist.", duration=3)
            return
        rel = os.path.relpath(abs_path, self.current_folder) if self.current_folder else abs_path
        editor = self._find_code_command()
        if editor:
            try:
                subprocess.Popen([editor, abs_path])
                self.show_info(f"Opening in VS Code: {rel}", duration=2)
                return
            except OSError as exc:
                log(f"[open_path] could not launch VS Code via '{editor}': {exc}")
        try:
            if sys.platform.startswith("win"):
                os.startfile(abs_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", abs_path])
            else:
                subprocess.Popen(["xdg-open", abs_path])
            self.show_info(f"Opened via default app: {rel}", duration=2)
        except Exception as exc:
            self.show_info("Unable to open file in editor.", duration=4)
            log(f"[open_path] fallback failed: {exc}")

    def _find_code_command(self) -> str | None:
        for candidate in ("code.cmd", "code"):
            path = shutil.which(candidate)
            if path:
                return path
        return None

    def update_path_table(self, paths: list[str]) -> None:
        if not self.path_table:
            return
        self.path_table.setRowCount(0)
        self.current_table_paths = list(paths)
        folder = self.current_folder
        all_valid = set(self.all_paths)
        stale = {p for p in self.selected_paths if p not in all_valid}
        if stale:
            self.selected_paths -= stale
            self._persist_selected_paths()
        for idx, path in enumerate(self.current_table_paths, start=1):
            rel = path
            if folder:
                try:
                    rel = os.path.relpath(path, folder)
                except ValueError:
                    rel = path
            line_count = self._line_count(path)
            filter_marker = "[x]" if path in self.filter_selected_paths else "[ ]"
            output_marker = "[x]" if path in self.selected_paths else "[ ]"
            row_idx = self.path_table.rowCount()
            self.path_table.insertRow(row_idx)
            self.path_table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(filter_marker))
            self.path_table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(output_marker))
            self.path_table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(str(idx)))
            rel_item = QtWidgets.QTableWidgetItem(rel)
            rel_item.setData(QtCore.Qt.UserRole, path)
            self.path_table.setItem(row_idx, 3, rel_item)
            self.path_table.setItem(
                row_idx,
                4,
                QtWidgets.QTableWidgetItem("" if line_count is None else str(line_count)),
            )
        self._update_copy_line_metrics()

    def sync_tree_checkboxes(self) -> None:
        if not self.tree_items:
            return
        self._suppress_tree_signal = True
        try:
            for path, item in self.tree_items.items():
                if path == self.current_folder:
                    continue
                should_check = path in self.selected_paths
                item.setCheckState(0, QtCore.Qt.Checked if should_check else QtCore.Qt.Unchecked)
        finally:
            self._suppress_tree_signal = False

    def _set_subtree_checkstate(self, item: QtWidgets.QTreeWidgetItem, state: QtCore.Qt.CheckState) -> None:
        for child_index in range(item.childCount()):
            child = item.child(child_index)
            child.setCheckState(0, state)
            self._set_subtree_checkstate(child, state)

    def _collect_descendant_paths(self, item: QtWidgets.QTreeWidgetItem) -> list[str]:
        paths: list[str] = []
        for child_index in range(item.childCount()):
            child = item.child(child_index)
            path = child.data(0, self.TREE_PATH_ROLE)
            if isinstance(path, str):
                paths.append(path)
            paths.extend(self._collect_descendant_paths(child))
        return paths

    def _line_count(self, path: str) -> int | None:
        if path in self.line_count_cache:
            return self.line_count_cache[path]
        if not os.path.isfile(path):
            return None
        try:
            if path in self.file_cache:
                count = self.file_cache[path].count("\n") + 1
            else:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    count = sum(1 for _ in handle)
            self.line_count_cache[path] = count
            return count
        except OSError:
            return None

    def _update_ascii_overview(self) -> None:
        if not self.ascii_view:
            return
        folder = self.current_folder
        if not folder:
            self.ascii_view.setPlainText("(no folder selected)")
            return
        text = build_ascii_tree_text(folder, self.get_ignore_patterns())
        self.ascii_view.setPlainText(text)

    def _persist_last_folder(self) -> None:
        if self.current_folder:
            self.settings.setValue("scope/lastFolder", self.current_folder)
        else:
            self.settings.remove("scope/lastFolder")

    def _persist_selected_paths(self) -> None:
        self.settings.setValue("selection/paths", sorted(self.selected_paths))

    def _startup_load(self) -> None:
        if self.current_folder and os.path.isdir(self.current_folder):
            self.refresh_tree()
        else:
            self.show_info("Choose a folder to load context.")

    def _sanitize_path(self, raw: str | None) -> str:
        if not raw:
            return ""
        return os.path.abspath(raw)

    def _read_list_setting(self, key: str) -> list[str]:
        value = self.settings.value(key, [])
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, (list, tuple)):
            cleaned = []
            for item in value:
                text = str(item).strip()
                if text:
                    cleaned.append(text)
            return cleaned
        return []

    def _initial_ignore_patterns(self) -> list[str]:
        stored = self._read_list_setting("scope/ignorePatterns")
        return stored or self.default_ignore_patterns

    def _maybe_migrate_legacy_config(self) -> None:
        migrated = self.settings.value("legacy/imported")
        if migrated:
            return
        legacy_path = Path(__file__).with_name("ignore_patterns.json")
        if not legacy_path.exists():
            self.settings.setValue("legacy/imported", True)
            return
        try:
            with open(legacy_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            log(f"[legacy] could not read {legacy_path}: {exc}")
            self.settings.setValue("legacy/imported", True)
            return

        if isinstance(data, list):
            patterns = [str(item).strip() for item in data if str(item).strip()]
            if patterns:
                self.settings.setValue("scope/ignorePatterns", patterns)
        elif isinstance(data, dict):
            patterns = data.get("ignore_patterns")
            if isinstance(patterns, list):
                cleaned = [str(item).strip() for item in patterns if str(item).strip()]
                if cleaned:
                    self.settings.setValue("scope/ignorePatterns", cleaned)
            last_folder = data.get("last_folder")
            if isinstance(last_folder, str) and last_folder.strip():
                self.settings.setValue("scope/lastFolder", last_folder.strip())
            selected_paths = data.get("selected_paths")
            if isinstance(selected_paths, list):
                cleaned_sel = [str(item).strip() for item in selected_paths if str(item).strip()]
                if cleaned_sel:
                    self.settings.setValue("selection/paths", cleaned_sel)

        self.settings.setValue("legacy/imported", True)
        self.settings.sync()
