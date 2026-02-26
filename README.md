# ANC Data Processing Software

A modular desktop application for processing **Ancorelog hyperspectral core scan data**.
It provides a Tkinter GUI with seven processing pipelines covering HSI extraction,
reflectance correction, coregistration, masking, XRF processing, RGB extraction,
and depth overlap correction.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Project Structure](#project-structure)
- [Processing Pipelines](#processing-pipelines)
- [Expected Folder Structure](#expected-folder-structure)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, make sure the following are installed on your system:

- **Python 3.9 or higher** — [Download Python](https://www.python.org/downloads/)
- **Git** — [Download Git](https://git-scm.com/downloads)
- **pip** (comes bundled with Python)

To check your Python version:

```bash
python --version
```

---

## Installation

Follow these steps exactly after cloning the repository.

### Step 1 — Clone the repository

```bash
git clone https://10.21.213.195/ancorelog/anc-data-processing.git
cd anc-data-processing
```

### Step 2 — Create a virtual environment

A virtual environment keeps all dependencies isolated from your system Python.

```bash
python -m venv venv
```

Activate it:

```bash
# On Windows
venv\Scripts\activate

# On Linux / macOS
source venv/bin/activate
```

You should see `(venv)` appear at the start of your terminal prompt.

### Step 3 — Install PyTorch (do this BEFORE requirements.txt)

PyTorch must be installed separately because the correct version depends on
whether your machine has an NVIDIA GPU (CUDA) or not.

**Option A — CPU only (no GPU):**

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**Option B — GPU with CUDA 11.8:**

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

**Option C — GPU with CUDA 12.1:**

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

> Not sure which version to pick? Use the selector at https://pytorch.org/get-started/locally/

### Step 4 — Install all remaining dependencies

```bash
pip install -r requirements.txt
```

This installs all required packages at the exact versions the software was
developed and tested with. PyTorch (installed in Step 3) will be skipped
automatically since it is already satisfied.

---

## Configuration

Before running the application, open `config.py` and update the three path
constants to match your local machine:

```python
# config.py

# Path to the Azure Tkinter theme file
THEME_PATH_FALLBACK = r"C:\path\to\azure.tcl"

# Path to the affine transform parameters file for SWIR/VNIR coregistration
TRANSFORM_PARAMETERS_FILE = r"C:\path\to\transform_parameters.txt"

# Path to the pre-trained PyTorch model file for HSI masking
MASK_MODEL_PATH = r"C:\path\to\your_model.pth"
```

| Constant | What it points to | When it is used |
|---|---|---|
| `THEME_PATH_FALLBACK` | `azure.tcl` from the Azure TTK theme folder | Every launch (GUI styling) |
| `TRANSFORM_PARAMETERS_FILE` | A `.txt` file with a 3x3 affine matrix (one row per line) | Step 3 — Coregister |
| `MASK_MODEL_PATH` | A `.pth` PyTorch model checkpoint | Step 4 — Mask HSI |

> The `azure.tcl` theme file is included in the repository under:
> `tkinter_themes/Azure-ttk-theme-main/azure.tcl`
> Point `THEME_PATH_FALLBACK` to that file.

---

## Running the Application

With the virtual environment active and `config.py` configured, run:

```bash
python main.py
```

The GUI window will open. Use the **Browse** buttons to set your input paths,
then click the processing buttons in order.

---

## Project Structure

```
anc-data-processing/
│
├── main.py                  # Entry point — run this file to launch the app
├── config.py                # Global path constants — edit before first run
├── utils.py                 # Shared helpers (buffered I/O, stdout redirector)
│
├── extraction.py            # CODE 1 — Extract & rename files from .ancprj archives
├── reflectance.py           # CODE 2 — HSI reflectance correction using white panels
├── coregistration.py        # CODE 3 — SWIR/VNIR coregistration via affine transform
├── masking.py               # CODE 4 — HSI masking with pre-trained PyTorch model
├── xrf_processing.py        # CODE 5 — XRF XML parsing, calibration & Excel export
├── rgb_extraction.py        # CODE 6 — RGB core piece extraction & enhancement
├── depth_overlap.py         # CODE 7 — Depth overlap detection & correction
│
├── gui.py                   # Tkinter window layout, widgets & button wiring
│
├── tkinter_themes/
│   └── Azure-ttk-theme-main/
│       └── azure.tcl        # GUI dark/light theme
│
├── requirements.txt         # Pinned Python dependencies
└── README.md
```

---

## Processing Pipelines

The GUI provides seven processing buttons. They are designed to be run
in order for a complete workflow, though each can also be run independently.

| # | Button | Module | What it does |
|---|---|---|---|
| 1 | Extract Files from ANCPRJ | `extraction.py` | Unzips `.ancprj` archives, pads HSI data to 384 samples, writes ENVI HDR metadata files |
| 2 | Correct HSI Files | `reflectance.py` | Loads white reference panel data, calibrates and applies reflectance correction to both SWIR and VNIR cubes |
| 3 | Coregister VNIR/SWIR Data | `coregistration.py` | Aligns SWIR and VNIR cubes using a pre-defined affine transform matrix and stitches them into a single composite |
| 4 | Mask HSI Files | `masking.py` | Runs a segmentation model in a subprocess to generate binary masks and zero out background pixels in HSI data |
| 5 | Compile XRF Data | `xrf_processing.py` | Parses XRF XML result files, applies element calibration formulas and exports a formatted Excel report |
| 6 | Extract RGB Core Pieces | `rgb_extraction.py` | Crops individual core piece images from full-box RGB scans, applies enhancement and matches them to HSI filenames |
| 7 | Make Depth Overlap Correction | `depth_overlap.py` | Detects depth overlaps between consecutive core boxes and corrects stop positions in XML and HDR files |

---

## Expected Folder Structure

The **Folder Path of ancprj** input should point to a project root folder.
Sub-folders are created automatically by each processing step:

```
<your_project_folder>/
│
├── *.ancprj                 <- Input: raw archive files (used by Step 1)
│
├── SWIR_HSI_Files/          <- Created by Step 1
├── VNIR_HSI_Files/          <- Created by Step 1
├── Extracted_WR/            <- Created by Step 1 (white reference files)
│
├── Corrected_SWIR/          <- Created by Step 2
├── Corrected_VNIR/          <- Created by Step 2
│
├── Coregistered_HSI/        <- Created by Step 3
│
└── Masked_HSI/              <- Created by Step 4
    ├── false_RGB/
    └── false_RGB_Masks/
```

---

## Troubleshooting

**The GUI does not open / theme error**
> Update `THEME_PATH_FALLBACK` in `config.py` to point to the correct
> `azure.tcl` file inside the `tkinter_themes` folder of this repository.

**"Model file not found" error on masking**
> Update `MASK_MODEL_PATH` in `config.py` to the full path of your `.pth` file.

**"Failed to load transform parameters" error on coregistration**
> Update `TRANSFORM_PARAMETERS_FILE` in `config.py`. The file must contain
> a 3x3 affine matrix — three rows, three space-separated float values per row.

**PyTorch installs CPU version even though I have a GPU**
> Make sure you installed PyTorch using the correct CUDA URL in Step 3
> *before* running `pip install -r requirements.txt`.

**Import errors when running**
> Make sure your virtual environment is activated (`(venv)` in terminal prompt)
> and that you ran `pip install -r requirements.txt` successfully.
