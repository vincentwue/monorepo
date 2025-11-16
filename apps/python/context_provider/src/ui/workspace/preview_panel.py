from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from copy_actions import copy_context, copy_selected, copy_signatures


class PreviewPanelMixin:
    """Result preview pane plus copy helpers."""

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
