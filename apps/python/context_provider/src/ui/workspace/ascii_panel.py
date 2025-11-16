from __future__ import annotations

from PySide6 import QtWidgets

from file_tree import build_ascii_tree_text


class AsciiPanelMixin:
    """ASCII folder overview panel."""

    def _build_ascii_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(QtWidgets.QLabel("ASCII Directory Overview"))

        self.ascii_view = QtWidgets.QPlainTextEdit()
        self.ascii_view.setReadOnly(True)
        self.ascii_view.setFont(self._monospace_font())
        layout.addWidget(self.ascii_view, 1)
        return panel

    def _update_ascii_overview(self) -> None:
        if not self.ascii_view:
            return
        folder = self.current_folder
        if not folder:
            self.ascii_view.setPlainText("(no folder selected)")
            return
        text = build_ascii_tree_text(folder, self.get_ignore_patterns())
        self.ascii_view.setPlainText(text)
