#!/usr/bin/env python3
"""
Context Provider Entry Point
"""
import sys
import os

# --- Windows Taskbar Icon Fix -----------------------------------------
if sys.platform.startswith("win"):
    try:
        import ctypes
        myappid = "ContextProvider.App"  # arbitrary unique string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        print("[LOG] Set Windows AppUserModelID for custom taskbar icon")
    except Exception as e:
        print(f"[WARN] Could not set AppUserModelID: {e}")
# ----------------------------------------------------------------------



from ui import FolderTreeApp

def main():
    print("[LOG] Starting FolderTreeApp…")
    app = FolderTreeApp()
    app.mainloop()
    print("[LOG] App closed.")


if __name__ == "__main__":
    main()
