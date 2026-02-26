"""
utils.py – Shared I/O helpers and stdout redirector used across all modules.
"""
import tkinter as tk


def open_with_buffer(filename, mode, buffering=2**20):
    """
    Same as open(filename, mode), but sets a large buffering (1 MB by default).
    Does not change any logic or outputs — only speeds up I/O.
    """
    return open(filename, mode, buffering=buffering)


class TextRedirector:
    """Redirects sys.stdout writes to a Tkinter Text widget in real time."""
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, s):
        self.widget.insert(tk.END, s)
        self.widget.see(tk.END)
        self.widget.update_idletasks()

    def flush(self):
        self.widget.update_idletasks()
        pass
