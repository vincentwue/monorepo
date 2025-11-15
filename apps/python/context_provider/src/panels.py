import tkinter as tk
from tkinter import ttk

from copy_actions import copy_selected, copy_context, copy_signatures


def build_ignore_panel(app, parent):
    frame = ttk.Frame(parent, padding=6)
    frame.rowconfigure(1, weight=1)
    frame.columnconfigure(0, weight=1)
    parent.add(frame, weight=0)

    ttk.Label(frame, text="Ignore Patterns").grid(row=0, column=0, sticky="w")
    text_frame = ttk.Frame(frame)
    text_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 4))

    scroll = ttk.Scrollbar(text_frame, orient="vertical")
    app.ignore_text = tk.Text(
        text_frame, wrap="none", font=("Consolas", 10), yscrollcommand=scroll.set
    )
    app.ignore_text.pack(side="left", fill="both", expand=True)
    scroll.config(command=app.ignore_text.yview)
    scroll.pack(side="right", fill="y")

    initial_patterns = app.config_data.get("ignore_patterns")
    if initial_patterns is not None:
        app._set_ignore_editor(initial_patterns)
    else:
        app.reset_ignore_patterns(refresh=False, persist=False)

    button_row = ttk.Frame(frame)
    button_row.grid(row=2, column=0, sticky="ew")
    button_row.columnconfigure(0, weight=1)
    button_row.columnconfigure(1, weight=1)

    ttk.Button(button_row, text="Apply & Refresh", command=app.apply_ignore_patterns).grid(
        row=0, column=0, sticky="ew", padx=(0, 4)
    )
    ttk.Button(button_row, text="Reset to Defaults", command=app.reset_ignore_patterns).grid(
        row=0, column=1, sticky="ew"
    )
    ttk.Label(frame, text="One pattern per line (substring match).").grid(
        row=3, column=0, sticky="w", pady=(4, 0)
    )

    return frame


def build_middle_panel(app, parent, pane_manager):
    split = ttk.PanedWindow(parent, orient="horizontal")
    parent.add(split, weight=1)

    _build_path_panel(app, split, pane_manager)
    _build_tree_area(app, split)
    _build_ascii_panel(app, split)

    return split


def build_result_panel(app, parent):
    frame = ttk.Frame(parent, padding=6)
    frame.rowconfigure(2, weight=1)
    frame.columnconfigure(0, weight=1)
    parent.add(frame, weight=1)

    ttk.Label(frame, text="Copy & Preview").grid(row=0, column=0, sticky="w")
    buttons = ttk.Frame(frame)
    buttons.grid(row=1, column=0, sticky="ew", pady=(4, 4))
    buttons.columnconfigure((0, 1, 2), weight=1)

    ttk.Button(buttons, text="Copy Selected", command=lambda: copy_selected(app)).grid(
        row=0, column=0, sticky="ew", padx=(0, 4)
    )
    ttk.Button(buttons, text="Copy Context", command=lambda: copy_context(app)).grid(
        row=0, column=1, sticky="ew", padx=(0, 4)
    )
    ttk.Button(buttons, text="Copy Signatures", command=lambda: copy_signatures(app)).grid(
        row=0, column=2, sticky="ew"
    )

    text_frame = ttk.Frame(frame)
    text_frame.grid(row=2, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(text_frame, orient="vertical")
    app.result_text = tk.Text(
        text_frame, wrap="none", font=("Consolas", 10), yscrollcommand=scroll.set
    )
    app.result_text.pack(side="left", fill="both", expand=True)
    scroll.config(command=app.result_text.yview)
    scroll.pack(side="right", fill="y")
    app.result_text.configure(state="disabled")
    app.update_result_preview("Use the copy buttons to preview output here.")
    return frame


def _build_path_panel(app, parent, pane_manager):
    panel = ttk.Frame(parent, padding=6)
    panel.rowconfigure(1, weight=1)
    panel.columnconfigure(0, weight=1)
    parent.add(panel, weight=0)

    ttk.Label(panel, text="Paths").grid(row=0, column=0, sticky="w")
    table_frame = ttk.Frame(panel)
    table_frame.grid(row=1, column=0, sticky="nsew")
    scroll_y = ttk.Scrollbar(table_frame, orient="vertical")
    scroll_x = ttk.Scrollbar(table_frame, orient="horizontal")
    app.path_table = ttk.Treeview(
        table_frame,
        columns=("select", "line", "path", "lines"),
        show="headings",
        selectmode="browse",
        yscrollcommand=scroll_y.set,
        xscrollcommand=scroll_x.set,
    )
    app.path_table.heading("select", text="Select")
    app.path_table.heading("line", text="#")
    app.path_table.heading("path", text="Relative Path")
    app.path_table.heading("lines", text="Lines")
    app.path_table.column("select", width=60, anchor="center")
    app.path_table.column("line", width=50, anchor="center")
    app.path_table.column("path", width=220, anchor="w")
    app.path_table.column("lines", width=60, anchor="center")
    app.path_table.grid(row=0, column=0, sticky="nsew")
    table_frame.rowconfigure(0, weight=1)
    table_frame.columnconfigure(0, weight=1)
    scroll_y.config(command=app.path_table.yview)
    scroll_y.grid(row=0, column=1, sticky="ns")
    scroll_x.config(command=app.path_table.xview)
    scroll_x.grid(row=1, column=0, sticky="ew")

    if pane_manager:
        pane_manager.track_table_columns(app.path_table, "path_table", ("select", "line", "path", "lines"))

    app.path_table.bind("<Double-1>", lambda e: app.open_path_from_table())
    app.path_table.bind("<Return>", lambda e: app.open_path_from_table())
    app.path_table.bind("<Button-1>", lambda e: app.handle_path_table_click(e), add="+")


def _build_tree_area(app, parent):
    frame = ttk.Frame(parent)
    parent.add(frame, weight=1)
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)

    app.canvas = tk.Canvas(frame)
    app.scroll = ttk.Scrollbar(frame, orient="vertical", command=app.canvas.yview)
    app.canvas.configure(yscrollcommand=app.scroll.set)
    app.scroll.pack(side="right", fill="y")
    app.canvas.pack(side="left", fill="both", expand=True)
    app.canvas.bind("<MouseWheel>", app._on_mousewheel)
    app.canvas.bind("<Button-4>", lambda e: app._on_mousewheel_linux(-1))
    app.canvas.bind("<Button-5>", lambda e: app._on_mousewheel_linux(1))

    app.inner_frame = ttk.Frame(app.canvas)
    app.canvas.create_window((0, 0), window=app.inner_frame, anchor="nw")
    app.inner_frame.bind(
        "<Configure>", lambda e: app.canvas.configure(scrollregion=app.canvas.bbox("all"))
    )


def _build_ascii_panel(app, parent):
    frame = ttk.Frame(parent, padding=6)
    parent.add(frame, weight=1)
    frame.rowconfigure(1, weight=1)
    frame.columnconfigure(0, weight=1)

    ttk.Label(frame, text="Project Tree Overview:").grid(row=0, column=0, sticky="w")
    text_frame = ttk.Frame(frame)
    text_frame.grid(row=1, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(text_frame, orient="vertical")
    app.ascii_text = tk.Text(
        text_frame, wrap="none", font=("Consolas", 10), yscrollcommand=scroll.set
    )
    app.ascii_text.pack(side="left", fill="both", expand=True)
    scroll.config(command=app.ascii_text.yview)
    scroll.pack(side="right", fill="y")
    app.ascii_text.configure(state="disabled")
