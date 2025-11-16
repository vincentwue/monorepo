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



from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from ui import ContextProviderWindow


def main():
    if load_dotenv is not None:
        load_dotenv()
    print("[LOG] Launching ContextProviderWindow")
    QCoreApplication.setOrganizationName("vincent")
    QCoreApplication.setOrganizationDomain("context-tool")
    QCoreApplication.setApplicationName("Context Provider")
    app = QApplication(sys.argv)
    window = ContextProviderWindow()
    window.show()
    exit_code = app.exec()
    print("[LOG] App closed.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
