from __future__ import annotations

import os
import shutil
import subprocess
import sys

from PySide6 import QtCore, QtWidgets

from utils import log


class TablePanelMixin:
    """Path table rendering, toggles, and helpers for opening files."""

    # NEW: helper so we have a single place to decide "is this a file?"
    def _is_file(self, path: str) -> bool:
        return os.path.isfile(path)

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
        layout.addWidget(self.path_table, 1)
        self.path_table.cellClicked.connect(self.handle_path_table_click)
        self.path_table.itemDoubleClicked.connect(self._handle_table_double_click)
        QtCore.QTimer.singleShot(0, self._restore_table_columns)
        return panel

    def select_all(self) -> None:
        # CHANGED: only select *files*, not directories
        base = self.current_table_paths or self.all_paths
        target = [p for p in base if self._is_file(p)]

        self.selected_paths = set(target)
        self._persist_selected_paths()
        self.update_path_table(self.current_table_paths or self.all_paths)
        self.sync_tree_checkboxes()
        self.show_info(f"Selected all {len(self.selected_paths)} file items.")
        self._update_copy_line_metrics()

    def deselect_all(self) -> None:
        self.selected_paths.clear()
        self._persist_selected_paths()
        self.update_path_table(self.current_table_paths or self.all_paths)
        self.sync_tree_checkboxes()
        self.show_info("Deselected all items.")
        self._update_copy_line_metrics()

    def select_search_results(self) -> None:
        # CHANGED: visible_filter_paths may contain folders; filter to files only
        base = self.visible_filter_paths or set(self.all_paths)
        targets = {p for p in base if self._is_file(p)}

        self.selected_paths.update(targets)
        self._persist_selected_paths()
        self.update_path_table(self.current_table_paths or self.all_paths)
        self.sync_tree_checkboxes()
        self.show_info(f"Selected {len(targets)} visible file paths.")
        self._update_copy_line_metrics()

    def select_filter_results(self) -> None:
        # CHANGED: same idea – only keep files
        base = self.visible_filter_paths or self.filter_selected_paths
        targets = {p for p in base if self._is_file(p)}

        if not targets:
            self.show_info("No filtered file paths to select.", duration=2)
            return
        self.selected_paths = set(targets)
        self._persist_selected_paths()
        self.update_path_table(self.current_table_paths or self.all_paths)
        self.sync_tree_checkboxes()
        self.show_info(f"Selected {len(targets)} filtered file paths.")
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
