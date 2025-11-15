from utils import log


class PaneManager:
    """Persist sizes for paned windows and table columns."""

    def __init__(self, app):
        self.app = app
        self._panes = {}

    # ------------------------------------------------------------------
    def register_pane(self, pane, key):
        if pane is None:
            return
        self._panes[key] = pane
        pane.bind("<ButtonRelease-1>", lambda e, p=pane, k=key: self._store_pane(p, k), add="+")
        self._apply_sashes_with_retry(pane, key)

    def _apply_sashes_with_retry(self, pane, key, attempt=0):
        if attempt > 12 or not pane.winfo_exists():
            return
        pane.update_idletasks()
        if not pane.panes():
            self.app.after(100, lambda: self._apply_sashes_with_retry(pane, key, attempt + 1))
            return
        success = self._restore_pane(pane, key)
        if not success:
            self.app.after(150, lambda: self._apply_sashes_with_retry(pane, key, attempt + 1))

    def force_restore(self):
        for key, pane in self._panes.items():
            if pane.winfo_exists():
                self._apply_sashes_with_retry(pane, key)

    # ------------------------------------------------------------------
    def track_table_columns(self, tree, key, columns):
        if tree is None:
            return
        config = self.app.config_data.setdefault("table_columns", {})

        # migrate legacy key from older builds
        if key == "path_table" and key not in config:
            legacy = self.app.config_data.pop("path_table_columns", None)
            if isinstance(legacy, dict):
                config[key] = legacy

        saved = config.get(key)
        if saved:
            for col, width in saved.items():
                try:
                    tree.column(col, width=int(width))
                except Exception:
                    pass

        def maybe_store(event=None):
            widths = {}
            for col in columns:
                try:
                    info = tree.column(col)
                    width = int(info.get("width", 0))
                    widths[col] = width
                except Exception:
                    continue
            if widths:
                config[key] = widths
                self.app._save_config()

        tree.bind("<ButtonRelease-1>", maybe_store, add="+")

    # ------------------------------------------------------------------
    def _store_pane(self, pane, key):
        panes = pane.panes()
        if len(panes) <= 1:
            return
        positions = []
        for idx in range(len(panes) - 1):
            try:
                pos = pane.sashpos(idx)
            except Exception:
                continue
            if isinstance(pos, (tuple, list)):
                pos = pos[0]
            try:
                positions.append(int(pos))
            except (TypeError, ValueError):
                continue
        if not positions:
            return
        self.app.config_data.setdefault("pane_sizes", {})[key] = positions
        self.app._save_config()

    # ------------------------------------------------------------------
    def _restore_pane(self, pane, key):
        try:
            positions = self.app.config_data.get("pane_sizes", {}).get(key)
        except AttributeError:
            return False
        if not positions:
            return False
        restored = False
        for idx, pos in enumerate(positions):
            try:
                pane.sashpos(idx, int(pos))
                restored = True
            except Exception as e:
                log(f"[PaneManager] Could not restore pane '{key}' sash {idx}: {e}")
        return restored
