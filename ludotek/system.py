"""Launching files and opening the file explorer, per OS."""
import os
import subprocess
import sys
import threading

from .config import IS_WIN
from .i18n import t

_PICKER = threading.Lock()  # one folder dialog at a time


def open_path(p):
    if IS_WIN:
        try:
            os.startfile(str(p), cwd=str(p.parent))  # Python 3.10+
        except TypeError:
            os.startfile(str(p))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])


def reveal_path(p):
    if IS_WIN:
        subprocess.Popen(f'explorer /select,"{p}"')
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p.parent if p.is_file() else p)])


def pick_folder(initial):
    """Native folder dialog (tkinter, standard library). Returns the path, or None if cancelled.

    Runs on the HTTP request thread and waits for the user, like a cover download.
    """
    unavailable = OSError(t("error.picker_unavailable"))
    if sys.platform == "darwin":
        raise unavailable  # Tk must run on the main thread on macOS
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError:
        raise unavailable
    if not _PICKER.acquire(blocking=False):
        raise OSError(t("error.picker_busy"))
    try:
        try:
            win = tkinter.Tk()
        except tkinter.TclError:
            raise unavailable
        try:
            win.withdraw()
            win.attributes("-topmost", True)  # otherwise it can open behind the browser
            path = filedialog.askdirectory(parent=win, initialdir=str(initial), mustexist=True)
        finally:
            win.destroy()
    finally:
        _PICKER.release()
    return os.path.normpath(path) if path else None
