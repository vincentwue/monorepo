from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from file_tree import build_ascii_from_paths
from filters import apply_filters as run_filters


class FilterPanelMixin:
    """Filter dock UI plus filtering orchestration."""

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

        result = run_filters(
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
