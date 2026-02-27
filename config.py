"""
config.py – Global constants and runtime configuration.
"""
import sys
from PIL import Image

# Theme path for GUI (fallback when not running as a PyInstaller bundle)
THEME_PATH_FALLBACK = r"\path\to\azure.tcl"

# Transform parameters file for coregistration
TRANSFORM_PARAMETERS_FILE = r"\path\to\transform_parameters.txt"

# Model path for HSI masking
MASK_MODEL_PATH = r"\path\to\your_model.pth"

# Allow processing of very large images
Image.MAX_IMAGE_PIXELS = None
