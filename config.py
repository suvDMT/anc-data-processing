"""
config.py – Global constants and runtime configuration.
"""
import sys
from PIL import Image

# Theme path for GUI (fallback when not running as a PyInstaller bundle)
THEME_PATH_FALLBACK = r"C:\path_to_themes\tkinter_themes\Azure-ttk-theme-main\azure.tcl"

# Transform parameters file for coregistration
TRANSFORM_PARAMETERS_FILE = r"D:\Filezilla\Coreg Essen\transform_parameters.txt"

# Model path for HSI masking
MASK_MODEL_PATH = r"D:\essen\05_06_2025_pth27.pth"

# Allow processing of very large images
Image.MAX_IMAGE_PIXELS = None
