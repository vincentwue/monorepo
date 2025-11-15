import os
import json
import subprocess
import shutil
import copy
import tkinter as tk
from tkinter import ttk, filedialog

from file_tree import build_tree, build_ascii_tree_text
from filters import apply_combined_filter
from ignore_patterns import IGNORE_PATTERNS
from pane_manager import PaneManager
from panels import build_ignore_panel, build_middle_panel, build_result_panel
from utils import log, update_text_widget


class FolderTreeApp(tk.Tk):
    DEFAULT_PANE_SIZES = {
        "main_split": [189, 1450],
        "tree_split": [432, 817],
    }
    DEFAULT_TABLE_COLUMNS = {
        "path_table": {"select": 60, "line": 47, "path": 297, "lines": 57},
    }

    def __init__(self):
        super().__init__()
        self.title("Context Provider")
        self.state("zoomed")
        self.ignore_text = None
        self.path_table = None
        self.result_text = None
        self.default_ignore_patterns = list(IGNORE_PATTERNS)
        self.base_dir = os.path.dirname(__file__)
        self.config_path = os.path.join(self.base_dir, "ignore_patterns.json")
        self.config_data = self._load_config()
        pane_changed = self._ensure_default_pane_sizes()
        column_changed = self._ensure_default_table_columns()
        if pane_changed or column_changed:
            self._save_config()
        self.initial_folder = self.config_data.get("last_folder", "")
        self.pane_manager = PaneManager(self)
        self.line_count_cache = {}
        self.selected_paths = set()
        self.current_table_paths = []
        
              # --- Modern icon setup ------------------------------------------
        icon_path = os.path.join(self.base_dir, "assets", "app_icon.png")
        
        if os.path.exists(icon_path):
            try:
                # Works across platforms (TkPhotoImage works for PNG)
                icon_img = tk.PhotoImage(file=icon_path)
                self.iconphoto(False, icon_img)
                print(f"[LOG] App icon loaded: {icon_path}")
            except Exception as e:
                print(f"[WARN] Could not load app icon: {e}")
        else:
            print(f"[WARN] Icon not found at {icon_path}")

        self.row_widgets = []  # (path, frame, depth)
        self.all_paths = []
        self.file_cache = {}
        self.filter_job = None
        self.info_clear_job = None

        self._make_ui()
        self.after(800, self.pane_manager.force_restore)
        self.after(200, self._startup_load)

    # ----------------------------------------------------------------------
    def _make_ui(self):
        top = ttk.Frame(self, padding=6)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        self.path_var = tk.StringVar(value=self.initial_folder)
        ttk.Entry(top, textvariable=self.path_var).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(top, text="Choose Folder...", command=self.choose_folder).grid(row=0, column=1, padx=3)
        ttk.Button(top, text="Load Content", command=self.load_content).grid(row=0, column=2, padx=3)

        # --- Search boxes --------------------------------------------------
        controls = ttk.Frame(self, padding=(6, 3))
        controls.grid(row=1, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Path Search:").grid(row=0, column=0, sticky="w")
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(controls, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky="ew", padx=4)
        search_entry.bind("<KeyRelease>", lambda e: self.apply_filter())

        ttk.Button(controls, text="Select All", command=self.select_all).grid(row=0, column=2, padx=2)
        ttk.Button(controls, text="Deselect All", command=self.deselect_all).grid(row=0, column=3, padx=2)
        ttk.Button(controls, text="Select Search Results", command=self.select_search_results).grid(row=0, column=4, padx=2)

        # --- In-File Search -----------------------------------------------
        in_file_frame = ttk.Frame(self, padding=(6, 3))
        in_file_frame.grid(row=2, column=0, sticky="ew")
        in_file_frame.columnconfigure(1, weight=1)
        ttk.Label(in_file_frame, text="In-File Search:").grid(row=0, column=0, sticky="w")
        self.file_search_var = tk.StringVar()
        in_file_entry = ttk.Entry(in_file_frame, textvariable=self.file_search_var)
        in_file_entry.grid(row=0, column=1, sticky="ew", padx=4)
        in_file_entry.bind("<KeyRelease>", lambda e: self.schedule_content_filter())

        # --- Info bar (replaces messagebox) -------------------------------
        self.info_label = ttk.Label(self, text="", foreground="#008800")
        self.info_label.grid(row=3, column=0, sticky="ew", padx=8, pady=(2, 4))

        # --- Main split: ignore editor | tree panes | results preview -----
        main_split = ttk.PanedWindow(self, orient="horizontal")
        main_split.grid(row=4, column=0, sticky="nsew")
        self.rowconfigure(4, weight=1)
        self.columnconfigure(0, weight=1)

        build_ignore_panel(self, main_split)
        tree_split = build_middle_panel(self, main_split, self.pane_manager)
        build_result_panel(self, main_split)

        self.pane_manager.register_pane(main_split, "main_split")
        self.pane_manager.register_pane(tree_split, "tree_split")

    # ----------------------------------------------------------------------
    def _startup_load(self):
        folder = self.initial_folder
        if folder and os.path.isdir(folder):
            self.path_var.set(folder)
            self.load_content()
        else:
            self.choose_folder()

    # ----------------------------------------------------------------------
    def show_info(self, msg, duration=3):
        """Show a non-blocking info message in the label bar."""
        log(f"INFO: {msg}")
        self.info_label.config(text=msg)
        if self.info_clear_job:
            self.after_cancel(self.info_clear_job)
        self.info_clear_job = self.after(duration * 1000, lambda: self.info_label.config(text=""))

    # ----------------------------------------------------------------------
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")

    def _on_mousewheel_linux(self, direction):
        self.canvas.yview_scroll(direction, "units")

    # ----------------------------------------------------------------------
    def choose_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        log(f"Folder selected: {folder}")
        self.path_var.set(folder)
        self.show_info("Folder selected. Click 'Load Content' to render.", duration=3)
        self._persist_last_folder()

    def load_content(self):
        """Trigger a manual refresh using the selected folder path."""
        self._persist_last_folder()
        self.refresh_tree()

    # ----------------------------------------------------------------------
    def _set_ignore_editor(self, patterns):
        if self.ignore_text is None:
            return
        self.ignore_text.delete("1.0", "end")
        self.ignore_text.insert("1.0", "\n".join(patterns))

    def _sanitize_patterns(self, raw):
        if not isinstance(raw, list):
            return None
        cleaned = []
        for item in raw:
            text = item if isinstance(item, str) else str(item)
            text = text.strip()
            if text:
                cleaned.append(text)
        return cleaned

    def _load_config(self):
        """Read persisted config (ignore patterns, last folder)."""
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log(f"[WARN] Failed to read config {self.config_path}: {e}")
            return {}

        if isinstance(data, list):
            patterns = self._sanitize_patterns(data)
            return {"ignore_patterns": patterns or []}

        if not isinstance(data, dict):
            return {}

        config = {}
        patterns = self._sanitize_patterns(data.get("ignore_patterns"))
        if patterns is not None:
            config["ignore_patterns"] = patterns
        last_folder = data.get("last_folder")
        if isinstance(last_folder, str) and last_folder.strip():
            config["last_folder"] = last_folder.strip()
        if "pane_sizes" in data:
            config["pane_sizes"] = data.get("pane_sizes") or {}
        if "table_columns" in data:
            config["table_columns"] = data.get("table_columns") or {}
        return config

    def _ensure_default_pane_sizes(self):
        pane_sizes = self.config_data.setdefault("pane_sizes", {})
        changed = False
        for key, values in self.DEFAULT_PANE_SIZES.items():
            if key not in pane_sizes:
                pane_sizes[key] = list(values)
                changed = True
        return changed

    def _ensure_default_table_columns(self):
        table_data = self.config_data.setdefault("table_columns", {})
        changed = False
        for key, cols in self.DEFAULT_TABLE_COLUMNS.items():
            table = table_data.setdefault(key, {})
            for col_name, width in cols.items():
                if col_name not in table:
                    table[col_name] = width
                    changed = True
        return changed

    def _save_config(self):
        """Persist configuration to disk."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2)
            log(f"Saved config -> {self.config_path}")
        except Exception as e:
            log(f"[WARN] Could not save config: {e}")
            self.show_info("Could not save settings to disk.", duration=3)

    def _persist_last_folder(self):
        folder = self.path_var.get().strip()
        if folder:
            self.config_data["last_folder"] = folder
        else:
            self.config_data.pop("last_folder", None)
        self._save_config()

    def open_path_from_table(self):
        if not self.path_table:
            return
        item = self.path_table.focus()
        if not item:
            return
        full_path = self.path_table.item(item, "text")
        rel_path = self.path_table.set(item, "path")
        folder = self.path_var.get().strip()
        if not full_path:
            if folder and rel_path:
                full_path = os.path.join(folder, rel_path)
            else:
                full_path = rel_path
        if not full_path:
            self.show_info("No path associated with this row.", duration=3)
            return
        abs_path = os.path.abspath(full_path)
        if not os.path.exists(abs_path):
            self.show_info("Selected path does not exist.", duration=3)
            return
        editor_cmd = self._find_code_command()
        opened = False
        if editor_cmd:
            try:
                subprocess.Popen([editor_cmd, abs_path])
                opened = True
                self.show_info(f"Opening in VS Code: {rel_path or abs_path}", duration=2)
            except Exception as e:
                log(f"[WARN] Could not launch VS Code via '{editor_cmd}': {e}")
        if not opened:
            if hasattr(os, "startfile"):
                try:
                    os.startfile(abs_path)
                    opened = True
                    self.show_info(f"Opened via default app: {rel_path or abs_path}", duration=2)
                except OSError as e:
                    log(f"[WARN] os.startfile failed: {e}")
            if not opened:
                self.show_info("Unable to open file in editor.", duration=4)

    def _find_code_command(self):
        candidates = ["code.cmd", "code.exe", "code"]
        for cmd in candidates:
            path = shutil.which(cmd)
            if path:
                return path
        local = os.environ.get("LOCALAPPDATA")
        if local:
            extra = [
                os.path.join(local, "Programs", "Microsoft VS Code", "bin", "code.cmd"),
                os.path.join(local, "Programs", "Microsoft VS Code", "Code.exe"),
            ]
            for path in extra:
                if os.path.exists(path):
                    return path
        return None

    # ----------------------------------------------------------------------
    def reset_ignore_patterns(self, refresh=True, patterns=None, persist=True):
        """Restore the default ignore list."""
        if self.ignore_text is None:
            return
        if patterns is None:
            patterns = list(self.default_ignore_patterns)
        self._set_ignore_editor(patterns)
        if persist:
            self.config_data["ignore_patterns"] = patterns
            self._save_config()
        if refresh:
            self.refresh_tree(patterns)
            self.show_info("Ignore patterns reset to defaults.", duration=2)

    # ----------------------------------------------------------------------
    def get_ignore_patterns(self):
        """Return the list currently entered in the ignore box."""
        if self.ignore_text is None:
            return list(self.default_ignore_patterns)
        lines = self.ignore_text.get("1.0", "end").splitlines()
        return [line.strip() for line in lines if line.strip()]

    # ----------------------------------------------------------------------
    def apply_ignore_patterns(self):
        """Apply edited ignore patterns and refresh the tree."""
        patterns = self.get_ignore_patterns()
        self.config_data["ignore_patterns"] = patterns
        self._save_config()
        self.refresh_tree(patterns)

    # ----------------------------------------------------------------------
    def refresh_tree(self, patterns=None):
        """Rebuild folder + ASCII tree using current ignore patterns."""
        folder = self.path_var.get().strip()
        if not folder:
            self.show_info("Choose a folder first to refresh.", duration=3)
            return
        if not os.path.isdir(folder):
            self.show_info("Selected folder is not available.", duration=3)
            return
        if patterns is None:
            patterns = self.get_ignore_patterns()

        log(f"Rendering tree for {folder} with {len(patterns)} ignore rules.")
        self.line_count_cache = {}
        build_tree(self, folder, patterns)
        ascii_output = build_ascii_tree_text(folder, patterns)
        update_text_widget(self.ascii_text, ascii_output)
        self.update_path_table(self.all_paths)
        self.show_info(f"Context refreshed with {len(patterns)} ignore patterns.", duration=2)
        log(f"ASCII tree refreshed for {folder}")


    # ----------------------------------------------------------------------
    def update_result_preview(self, text, title=None):
        """Display the latest copied output in the preview panel."""
        if self.result_text is None:
            return
        body = text or "(no data)"
        if title:
            header = f"{title}\n{'-' * len(title)}\n\n"
        else:
            header = ""
        update_text_widget(self.result_text, header + body)

    # ----------------------------------------------------------------------
    def _line_count(self, path):
        """Return cached line count for a file if available."""
        if path in self.line_count_cache:
            return self.line_count_cache[path]

        if not os.path.isfile(path):
            return None
        try:
            if path in self.file_cache:
                count = self.file_cache[path].count("\n") + 1
            else:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    count = sum(1 for _ in f)
            self.line_count_cache[path] = count
            return count
        except Exception:
            return None

    # ----------------------------------------------------------------------
    def update_path_table(self, paths):
        """Populate the path table with relative paths + line numbers."""
        if self.path_table is None:
            return
        for item in self.path_table.get_children():
            self.path_table.delete(item)

        self.current_table_paths = list(paths)
        all_valid = set(self.all_paths)
        self.selected_paths = {p for p in self.selected_paths if p in all_valid}

        if not self.current_table_paths:
            return

        folder = self.path_var.get().strip()
        for idx, path in enumerate(self.current_table_paths, start=1):
            rel = path
            if folder:
                try:
                    rel = os.path.relpath(path, folder)
                except ValueError:
                    rel = path
            line_count = self._line_count(path)
            line_display = "" if line_count is None else str(line_count)
            marker = "[x]" if path in self.selected_paths else "[ ]"
            self.path_table.insert("", "end", text=path, values=(marker, idx, rel, line_display))

    def handle_path_table_click(self, event):
        if not self.path_table:
            return
        region = self.path_table.identify("region", event.x, event.y)
        if region != "cell":
            return
        column = self.path_table.identify_column(event.x)
        if column != "#1":
            return
        item = self.path_table.identify_row(event.y)
        if not item:
            return "break"
        path = self.path_table.item(item, "text")
        if not path:
            return "break"
        self.toggle_path_selection(path)
        self.update_path_table(self.current_table_paths or self.all_paths)
        return "break"

    def toggle_path_selection(self, path):
        if path in self.selected_paths:
            self.selected_paths.remove(path)
        else:
            self.selected_paths.add(path)

    # ----------------------------------------------------------------------
    def apply_filter(self):
        apply_combined_filter(self)
        self.show_info("Filter applied and ASCII tree updated.", duration=2)


    def schedule_content_filter(self):
        if self.filter_job:
            self.after_cancel(self.filter_job)
        self.filter_job = self.after(400, self.apply_filter)

    # ----------------------------------------------------------------------
    def select_all(self):
        target = self.current_table_paths or self.all_paths
        self.selected_paths = set(target)
        self.update_path_table(target)
        msg = f"Selected all {len(self.selected_paths)} items."
        self.show_info(msg)

    def deselect_all(self):
        self.selected_paths.clear()
        self.update_path_table(self.current_table_paths or self.all_paths)
        self.show_info("Deselected all items.")

    def select_search_results(self):
        """Select only currently visible search results."""
        added = 0
        for path, row, depth in self.row_widgets:
            if str(row.grid_info()) != "{}":  # visible row
                if path not in self.selected_paths:
                    self.selected_paths.add(path)
                    added += 1
        self.update_path_table(self.current_table_paths or self.all_paths)
        msg = f"Selected {added} visible search results."
        self.show_info(msg)

