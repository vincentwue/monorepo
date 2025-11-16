from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ignore_patterns import IGNORE_PATTERNS
from utils import log


class WorkspaceStateMixin:
    """Core state/persistence helpers shared across workspace features."""

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

    def set_clipboard_text(self, text: str) -> None:
        self.clipboard.setText(text)

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
