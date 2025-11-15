import datetime



def log(msg):
    """Timestamped console log."""
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [LOG] {msg}")

def update_text_widget(widget, text: str):
    """Safely update a read-only text widget."""
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.configure(state="disabled")
