from __future__ import annotations

from .ascii_panel import AsciiPanelMixin
from .filter_panel import FilterPanelMixin
from .preview_panel import PreviewPanelMixin
from .scope_panel import ScopePanelMixin
from .state import WorkspaceStateMixin
from .table_panel import TablePanelMixin
from .tree_panel import TreePanelMixin

__all__ = ["WorkspaceMixin"]


class WorkspaceMixin(
    WorkspaceStateMixin,
    ScopePanelMixin,
    FilterPanelMixin,
    TreePanelMixin,
    TablePanelMixin,
    AsciiPanelMixin,
    PreviewPanelMixin,
):
    """Composition root mixing together the individual workspace features."""

    pass
