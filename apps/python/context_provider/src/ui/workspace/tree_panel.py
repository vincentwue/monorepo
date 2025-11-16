from __future__ import annotations

import os

from PySide6 import QtCore, QtWidgets

from file_tree import gather_tree_entries


class TreePanelMixin:
    """Directory tree display and selection sync."""

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

    def _update_tree_visibility(self, matched_paths: set[str], filters_active: bool) -> None:
        for path, item in self.tree_items.items():
            if path == self.current_folder:
                item.setHidden(False)
                continue
            hidden = filters_active and path not in matched_paths
            item.setHidden(hidden)

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
