from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets


class ScopePanelMixin:
    """Folder selection and ignore-pattern management."""

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
