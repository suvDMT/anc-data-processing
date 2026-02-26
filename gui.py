"""
gui.py – Tkinter window, all widgets, and button command wiring.
Imports processing callbacks from their respective modules and wires
them to GUI buttons using lambdas so widget values are passed at click time.
"""
import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from config import THEME_PATH_FALLBACK
from extraction     import rename_and_extract
from reflectance    import reflect_correct_hsi
from coregistration import coregister_hsi_optimized
from masking        import mask_hsi_files
from xrf_processing import start_processing_xml_combine
from rgb_extraction import extract_rgb_core_pieces
from depth_overlap  import adjust_depth_overlap


def build_gui():
    root = tk.Tk()
    root.title("Ancorelog Processing Software")

    # ── Theme ────────────────────────────────────────────────────────────────
    if hasattr(sys, '_MEIPASS'):
        theme_path = os.path.join(
            sys._MEIPASS, 'tkinter_themes', 'Azure-ttk-theme-main', 'azure.tcl')
    else:
        theme_path = THEME_PATH_FALLBACK
    root.tk.call('source', theme_path)
    root.tk.call("set_theme", "dark")

    # ── Input fields ─────────────────────────────────────────────────────────
    ttk.Label(root, text="Folder Path of ancprj:").grid(
        row=0, column=0, padx=20, pady=10, sticky='e')
    folder_entry = ttk.Entry(root, width=50)
    folder_entry.grid(row=0, column=1, padx=20, pady=10)
    ttk.Button(root, text="Browse", style='Accent.TButton',
               command=lambda: folder_entry.delete(0, tk.END) or
               folder_entry.insert(0, filedialog.askdirectory())
               ).grid(row=0, column=2, padx=20, pady=10)

    ttk.Label(root, text="XRF Calibration File:").grid(
        row=1, column=0, padx=20, pady=10, sticky='e')
    xrfcalib_entry = ttk.Entry(root, width=50)
    xrfcalib_entry.grid(row=1, column=1, padx=20, pady=10)
    ttk.Button(root, text="Browse", style='Accent.TButton',
               command=lambda: xrfcalib_entry.delete(0, tk.END) or
               xrfcalib_entry.insert(0, filedialog.askopenfilename(
                   filetypes=[("Text files", "*.txt")]))
               ).grid(row=1, column=2, padx=20, pady=10)

    ttk.Label(root, text="XML File location:").grid(
        row=2, column=0, padx=20, pady=10, sticky='e')
    xml_entry = ttk.Entry(root, width=50)
    xml_entry.grid(row=2, column=1, padx=20, pady=10)
    ttk.Button(root, text="Browse", style='Accent.TButton',
               command=lambda: xml_entry.delete(0, tk.END) or
               xml_entry.insert(0, filedialog.askopenfilename(
                   filetypes=[("XML files", "*.xml")]))
               ).grid(row=2, column=2, padx=20, pady=10)

    ttk.Label(root, text="Files to be Masked:").grid(
        row=3, column=0, padx=20, pady=10, sticky='e')
    mask_entry = ttk.Entry(root, width=50)
    mask_entry.grid(row=3, column=1, padx=20, pady=10)
    ttk.Button(root, text="Browse", style='Accent.TButton',
               command=lambda: mask_entry.delete(0, tk.END) or
               mask_entry.insert(0, filedialog.askdirectory())
               ).grid(row=3, column=2, padx=20, pady=10)

    for col in range(3):
        root.grid_columnconfigure(col, weight=1)

    # ── Button frame ─────────────────────────────────────────────────────────
    button_frame = ttk.Frame(root)
    button_frame.grid(row=6, column=0, columnspan=3, pady=10)
    button_frame.grid_columnconfigure(0, weight=1)
    button_frame.grid_columnconfigure(1, weight=1)

    # Left column
    ttk.Button(button_frame, text="Extract Files from ANCPRJ",
               style='Accent.TButton',
               command=lambda: rename_and_extract(
                   folder_entry.get(), log_text)
               ).grid(row=0, column=0, padx=10, pady=5, sticky='ew')

    ttk.Button(button_frame, text="Correct HSI Files",
               style='Accent.TButton',
               command=lambda: reflect_correct_hsi(
                   folder_entry.get(), log_text)
               ).grid(row=1, column=0, padx=10, pady=5, sticky='ew')

    ttk.Button(button_frame, text="Coregister VNIR/SWIR Data",
               style='Accent.TButton',
               command=lambda: coregister_hsi_optimized(
                   folder_entry.get(), log_text)
               ).grid(row=2, column=0, padx=10, pady=5, sticky='ew')

    ttk.Button(button_frame, text="Mask HSI Files",
               style='Accent.TButton',
               command=lambda: mask_hsi_files(
                   folder_entry.get(), mask_entry.get(), log_text)
               ).grid(row=3, column=0, padx=10, pady=5, sticky='ew')

    # Right column
    ttk.Button(button_frame, text="Compile XRF Data",
               style='Accent.TButton',
               command=lambda: start_processing_xml_combine(
                   folder_entry.get(), xml_entry.get(),
                   xrfcalib_entry.get(), log_text)
               ).grid(row=0, column=1, padx=10, pady=5, sticky='ew')

    ttk.Button(button_frame, text="Extract RGB Core Pieces",
               style='Accent.TButton',
               command=lambda: extract_rgb_core_pieces(
                   folder_entry.get(), xml_entry.get(), log_text)
               ).grid(row=1, column=1, padx=10, pady=5, sticky='ew')

    ttk.Button(button_frame, text="Make Depth Overlap Correction",
               style='Accent.TButton',
               command=lambda: adjust_depth_overlap(
                   folder_entry.get(), xml_entry.get(), log_text)
               ).grid(row=2, column=1, padx=10, pady=5, sticky='ew')

    # ── Log text widget ───────────────────────────────────────────────────────
    log_text = tk.Text(root, height=11, width=90)
    log_text.grid(row=12, column=0, columnspan=3, padx=10, pady=10)
    log_text.insert(tk.END, "Welcome to the Ancorelog Processor!\n")

    return root


def run_app():
    root = build_gui()
    root.mainloop()
