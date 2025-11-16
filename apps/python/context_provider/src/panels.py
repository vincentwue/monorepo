import tkinter as tk

import ttkbootstrap as ttk

from copy_actions import copy_selected, copy_context, copy_signatures


def build_ignore_panel(app, parent):
    frame = ttk.Frame(parent, padding=6)
    frame.columnconfigure(0, weight=1)

    ttk.Label(frame, text="Scope Settings").grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text="Base Folder").grid(row=1, column=0, sticky="w", pady=(4, 0))
    path_row = ttk.Frame(frame)
    path_row.grid(row=2, column=0, sticky="ew", pady=(4, 8))
    path_row.columnconfigure(0, weight=1)

    ttk.Entry(path_row, textvariable=app.path_var).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ttk.Button(path_row, text="Choose", command=app.choose_folder).grid(row=0, column=1, padx=(0, 4))
    ttk.Button(path_row, text="Load", command=app.load_content).grid(row=0, column=2)

    ttk.Label(frame, text="Ignore Patterns").grid(row=3, column=0, sticky="w")
    text_frame = ttk.Frame(frame)
    text_frame.grid(row=4, column=0, sticky="nsew", pady=(4, 4))
    frame.rowconfigure(4, weight=1)

    scroll = ttk.Scrollbar(text_frame, orient="vertical")
    app.ignore_text = tk.Text(text_frame, wrap="none", font=app.global_font, yscrollcommand=scroll.set)
    app.ignore_text.pack(side="left", fill="both", expand=True)
    scroll.config(command=app.ignore_text.yview)
    scroll.pack(side="right", fill="y")

    initial_patterns = app.config_data.get("ignore_patterns")
    if initial_patterns is not None:
        app._set_ignore_editor(initial_patterns)
    else:
        app.reset_ignore_patterns(refresh=False, persist=False)

    button_row = ttk.Frame(frame)
    button_row.grid(row=5, column=0, sticky="ew")
    button_row.columnconfigure(0, weight=1)
    button_row.columnconfigure(1, weight=1)

    ttk.Button(button_row, text="Apply & Refresh", command=app.apply_ignore_patterns).grid(
        row=0, column=0, sticky="ew", padx=(0, 4)
    )
    ttk.Button(button_row, text="Reset to Defaults", command=app.reset_ignore_patterns).grid(
        row=0, column=1, sticky="ew"
    )
    ttk.Label(frame, text="One pattern per line (substring match).").grid(
        row=6, column=0, sticky="w", pady=(4, 0)
    )

    return frame


def build_filter_panel(app, parent):
    frame = ttk.Frame(parent, padding=6)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(2, weight=1)
    frame.rowconfigure(5, weight=1)

    ttk.Label(frame, text="Filter Settings").grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text="In-File Includes (one substring per line)").grid(row=1, column=0, sticky="w")

    includes_frame = ttk.Frame(frame)
    includes_frame.grid(row=2, column=0, sticky="nsew", pady=(4, 6))
    scroll_include = ttk.Scrollbar(includes_frame, orient="vertical")
    app.file_include_text = tk.Text(
        includes_frame, wrap="none", font=app.global_font, yscrollcommand=scroll_include.set, height=6
    )
    app.file_include_text.pack(side="left", fill="both", expand=True)
    app.file_include_text.bind("<KeyRelease>", lambda e: app.schedule_content_filter())
    scroll_include.config(command=app.file_include_text.yview)
    scroll_include.pack(side="right", fill="y")

    include_buttons = ttk.Frame(frame)
    include_buttons.grid(row=3, column=0, sticky="ew", pady=(0, 8))
    include_buttons.columnconfigure((0, 1), weight=1)
    ttk.Button(include_buttons, text="Apply In-File Filter", command=app.apply_filter).grid(
        row=0, column=0, sticky="ew", padx=(0, 4)
    )
    ttk.Button(include_buttons, text="Clear In-File Filter", command=app.clear_infile_filters).grid(
        row=0, column=1, sticky="ew"
    )

    ttk.Label(frame, text="Path Filters (one per line)").grid(row=4, column=0, sticky="w")
    path_frame = ttk.Frame(frame)
    path_frame.grid(row=5, column=0, sticky="nsew", pady=(4, 4))
    scroll_path = ttk.Scrollbar(path_frame, orient="vertical")
    app.path_filter_text = tk.Text(
        path_frame, wrap="none", font=app.global_font, yscrollcommand=scroll_path.set, height=6
    )
    app.path_filter_text.pack(side="left", fill="both", expand=True)
    app.path_filter_text.bind("<KeyRelease>", lambda e: app.schedule_content_filter())
    scroll_path.config(command=app.path_filter_text.yview)
    scroll_path.pack(side="right", fill="y")

    path_buttons = ttk.Frame(frame)
    path_buttons.grid(row=6, column=0, sticky="ew")
    path_buttons.columnconfigure((0, 1), weight=1)
    ttk.Button(path_buttons, text="Apply Path Filter", command=app.apply_filter).grid(
        row=0, column=0, sticky="ew", padx=(0, 4)
    )
    ttk.Button(path_buttons, text="Clear Path Filter", command=app.clear_path_filters).grid(
        row=0, column=1, sticky="ew"
    )

    return frame


def build_middle_panel(app, parent, pane_manager):
    split = ttk.Panedwindow(parent, orient="horizontal")
    parent.add(split, weight=1)

    _build_path_panel(app, split, pane_manager)
    _build_tree_area(app, split)
    _build_ascii_panel(app, split)

    return split


def build_result_panel(app, parent):
    frame = ttk.Frame(parent, padding=6)
    frame.rowconfigure(1, weight=1)
    frame.columnconfigure(0, weight=1)
    parent.add(frame, weight=1)

    header = ttk.Label(frame, text="Copy Actions")
    header.grid(row=0, column=0, sticky="w")
    app.copy_button_header = header
    buttons = ttk.Frame(frame)
    buttons.grid(row=1, column=0, sticky="nsew")
    buttons.columnconfigure((0, 1, 2), weight=1)
    app.copy_button_panel = buttons

    ttk.Button(buttons, text="Copy Selected", command=lambda: copy_selected(app)).grid(
        row=0, column=0, sticky="ew", padx=(0, 4)
    )
    ttk.Button(buttons, text="Copy Context", command=lambda: copy_context(app)).grid(
        row=0, column=1, sticky="ew", padx=(0, 4)
    )
    ttk.Button(buttons, text="Copy Signatures", command=lambda: copy_signatures(app)).grid(
        row=0, column=2, sticky="ew"
    )
    return frame


def _build_path_panel(app, parent, pane_manager):
    panel = ttk.Frame(parent, padding=6)
    panel.rowconfigure(2, weight=1)
    panel.columnconfigure(0, weight=1)
    parent.add(panel, weight=0)
    app.table_panel = panel

    ttk.Label(panel, text="Path Selection Table").grid(row=0, column=0, sticky="w")

    button_row = ttk.Frame(panel)
    button_row.grid(row=1, column=0, sticky="ew", pady=(4, 6))
    button_row.columnconfigure((0, 1, 2, 3), weight=1)
    ttk.Button(button_row, text="Select All", command=app.select_all).grid(row=0, column=0, padx=2, sticky="ew")
    ttk.Button(button_row, text="Deselect All", command=app.deselect_all).grid(row=0, column=1, padx=2, sticky="ew")
    ttk.Button(button_row, text="Select Visible", command=app.select_search_results).grid(
        row=0, column=2, padx=2, sticky="ew"
    )
    ttk.Button(button_row, text="Use Filter Selection", command=app.select_filter_results).grid(
        row=0, column=3, padx=2, sticky="ew"
    )

    table_frame = ttk.Frame(panel)
    table_frame.grid(row=2, column=0, sticky="nsew")
    scroll_y = ttk.Scrollbar(table_frame, orient="vertical")
    scroll_x = ttk.Scrollbar(table_frame, orient="horizontal")
    columns = ("filter", "output", "line", "path", "lines")
    app.path_table = ttk.Treeview(
        table_frame,
        columns=columns,
        show="headings",
        selectmode="browse",
        yscrollcommand=scroll_y.set,
        xscrollcommand=scroll_x.set,
    )
    app.path_table.heading("filter", text="Filter")
    app.path_table.heading("output", text="Output")
    app.path_table.heading("line", text="#")
    app.path_table.heading("path", text="Relative Path")
    app.path_table.heading("lines", text="Lines")
    app.path_table.column("filter", width=70, anchor="center")
    app.path_table.column("output", width=80, anchor="center")
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
        pane_manager.track_table_columns(app.path_table, "path_table", columns)

    app.path_table.bind("<Double-1>", lambda e: app.open_path_from_table())
    app.path_table.bind("<Return>", lambda e: app.open_path_from_table())
    app.path_table.bind("<Button-1>", lambda e: app.handle_path_table_click(e), add="+")


def _build_tree_area(app, parent):
    panel = ttk.Frame(parent, padding=6)
    parent.add(panel, weight=1)
    app.tree_panel = panel
    panel.rowconfigure(1, weight=1)
    panel.columnconfigure(0, weight=1)

    ttk.Label(panel, text="Directory Tree Explorer").grid(row=0, column=0, sticky="w")

    frame = ttk.Frame(panel)
    frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)

    app.canvas = tk.Canvas(frame)
    app.scroll = ttk.Scrollbar(frame, orient="vertical", command=app.canvas.yview)
    app.canvas.configure(yscrollcommand=app.scroll.set)
    app.canvas.grid(row=0, column=0, sticky="nsew")
    app.scroll.grid(row=0, column=1, sticky="ns")
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
    frame.rowconfigure(2, weight=1)
    frame.columnconfigure((0, 1), weight=1)
    app.preview_panel = frame

    ttk.Label(frame, text="Overview & Preview").grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(frame, text="Project Tree Overview").grid(row=1, column=0, sticky="w")
    ttk.Label(frame, text="Preview Output").grid(row=1, column=1, sticky="w")

    # Left: ASCII overview
    ascii_frame = ttk.Frame(frame)
    ascii_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 6))
    ascii_frame.rowconfigure(0, weight=1)
    ascii_frame.columnconfigure(0, weight=1)
    scroll_left = ttk.Scrollbar(ascii_frame, orient="vertical")
    app.ascii_text = tk.Text(ascii_frame, wrap="none", font=app.global_font, yscrollcommand=scroll_left.set)
    app.ascii_text.grid(row=0, column=0, sticky="nsew")
    scroll_left.grid(row=0, column=1, sticky="ns")
    app.ascii_text.configure(state="disabled")
    scroll_left.config(command=app.ascii_text.yview)

    # Right: preview text area
    preview_frame = ttk.Frame(frame)
    preview_frame.grid(row=2, column=1, sticky="nsew")
    preview_frame.rowconfigure(0, weight=1)
    preview_frame.columnconfigure(0, weight=1)
    scroll_right = ttk.Scrollbar(preview_frame, orient="vertical")
    app.result_text = tk.Text(preview_frame, wrap="none", font=app.global_font, yscrollcommand=scroll_right.set)
    app.result_text.grid(row=0, column=0, sticky="nsew")
    scroll_right.grid(row=0, column=1, sticky="ns")
    app.result_text.configure(state="disabled")
    scroll_right.config(command=app.result_text.yview)
