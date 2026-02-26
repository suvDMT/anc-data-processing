"""
reflectance.py – CODE 2: Reflectance Correction
Calibrates white reference panels and applies reflectance correction to
SWIR and VNIR HSI files.
"""
import os, sys, glob, re
import numpy as np
import spectral.io.envi as envi
from tkinter import messagebox

from utils import open_with_buffer, TextRedirector


def load_envi_data(hdr_path, raw_path):
    """Load ENVI data from header and raw files"""
    with open(hdr_path, 'r') as f:
        contents = f.read()
    if "byte order" not in contents.lower():
        with open(hdr_path, 'a') as f:
            f.write("\nbyte order = 0\n")
    img = envi.open(hdr_path, raw_path)
    return img.load(), img.metadata

def get_output_filenames(input_hdr, output_folder):
    """Generate output filenames with _COR suffix"""
    base = os.path.splitext(os.path.basename(input_hdr))[0]
    new_base = base + "_COR"
    return os.path.join(output_folder, new_base + ".hdr"), os.path.join(output_folder, new_base + ".raw")

def load_panel_reflectance(panel_path):
    """Load panel reflectance data from CSV file"""
    print(f"Loading panel reflectance from: {panel_path}")
    
    try:
        # Read the file line by line
        with open(panel_path, 'r') as f:
            lines = f.readlines()
        
        if len(lines) < 3:
            raise ValueError("File has insufficient data lines")
        
        # Extract headers
        headers = lines[1].strip()
        
        if "nm" in headers and "%R" in headers:
            # Parse data lines
            wavelengths = []
            reflectances = []
            
            for line in lines[2:]:
                if not line.strip():
                    continue
                
                parts = line.strip().split(';')
                if len(parts) >= 2:
                    try:
                        wl = float(parts[0])
                        refl_str = parts[1].replace(',', '.')
                        refl = float(refl_str)
                        
                        wavelengths.append(wl)
                        reflectances.append(refl)
                    except ValueError:
                        continue
            
            if len(wavelengths) < 10:
                # Try alternative parsing if standard method fails
                for line in lines[2:]:
                    if not line.strip():
                        continue
                    for delimiter in [';', ',', ' ', '\t']:
                        parts = line.strip().split(delimiter)
                        if len(parts) >= 2:
                            try:
                                wl = float(parts[0])
                                refl_str = parts[1].replace(',', '.')
                                refl = float(refl_str)
                                wavelengths.append(wl)
                                reflectances.append(refl)
                                break
                            except:
                                continue
            
            if len(wavelengths) < 10:
                raise ValueError(f"Too few valid data points: {len(wavelengths)}")
            
            # Convert to numpy arrays
            nm = np.array(wavelengths, dtype=np.float32)
            ref_values = np.array(reflectances, dtype=np.float32)
            
            # Check if reflectance is in percentage
            if ref_values.max() > 1.5:
                ref = ref_values / 100
            else:
                ref = ref_values
            
            # Ensure reflectance values are between 0 and 1
            ref = np.clip(ref, 0, 1)
            
            print(f"Successfully loaded panel data: {len(nm)} points")
            return nm, ref
        else:
            raise ValueError("Expected column headers 'nm' and '%R' not found")
            
    except Exception as e:
        print(f"Error loading panel reflectance: {str(e)}")
        raise ValueError(f"Failed to parse panel data: {str(e)}")

def calibrate_white_reference(measured_white, white_meta, panel_nm, panel_ref):
    """Calibrate white reference using panel reflectance data"""
    w = measured_white.astype(np.float32)
    if "wavelength" not in white_meta:
        raise ValueError("No 'wavelength' in WR header.")
    band_centers = np.array([float(x) for x in white_meta["wavelength"]], dtype=np.float32)
    panel_vals = np.interp(band_centers, panel_nm, panel_ref).reshape((1, 1, -1))
    panel_vals[panel_vals < 1e-6] = 1e-6  # Avoid division by zero
    return w / panel_vals

def correct_raw_hsi_with_calibrated_wh(calib_white, raw_data):
    """Correct raw HSI data using calibrated white reference"""
    cwhite = calib_white.copy()
    cwhite[cwhite < 1e-6] = 1e-6  # Avoid division by zero
    raw_f32 = raw_data.astype(np.float32)
    return raw_f32 / cwhite


def update_metadata(meta):
    """Update metadata for corrected files"""
    meta["data type"] = 4  # float32
    meta["byte order"] = 0
    meta["interleave"] = "bil"
    meta["file type"] = "ENVI"
    return meta

def get_white_reference_for_hsi(hsi_folder, white_ref_dir, sensor_type):
    """Find matching white reference file for an HSI folder"""
    folder_name = os.path.basename(hsi_folder)
    m = re.match(r'^[^_]+_([^_]+(?:_[^_]+)?)_\{', folder_name)
    if not m:
        print(f"Could not extract token from folder: {folder_name}")
        return None, None, None
    
    token = m.group(1)
    candidates = []
    
    for file in os.listdir(white_ref_dir):
        if file.lower().endswith('.hdr') and sensor_type.lower() in file.lower():
            if token.lower() in file.lower() and "neoreftarget" in file.lower():
                wr_path = os.path.join(white_ref_dir, file)
                base = os.path.splitext(file)[0]
                raw_candidate = os.path.join(white_ref_dir, base + ".raw")
                if not os.path.exists(raw_candidate):
                    raw_candidate = os.path.join(white_ref_dir, base + ".envi")
                if os.path.exists(raw_candidate):
                    candidates.append((wr_path, raw_candidate))
    
    if candidates:
        wr_hdr, wr_raw = candidates[0]
        print(f"Using {sensor_type} WR with token '{token}'")
        return wr_hdr, wr_raw, token
    else:
        print(f"No matching {sensor_type} white reference for token '{token}'")
        return None, None, None

def get_reference_panel_definition(white_ref_dir, token, sensor_type):
    """Find matching reference panel definition file"""
    for file in os.listdir(white_ref_dir):
        if file.lower().endswith('.csv') and "referencepaneldefinition" in file.lower():
            if token.lower() in file.lower() and sensor_type.lower() in file.lower():
                panel_path = os.path.join(white_ref_dir, file)
                print(f"Using Reference Panel Definition for {sensor_type} with token '{token}'")
                return panel_path
    
    print(f"No matching Reference Panel Definition for {sensor_type} with token '{token}'")
    return None

def process_directory_with_calib(inp, outp, wr_dir, sensor_type):
    """Process a directory of HSI files with calibrated reflectance correction"""
    used_files = set()
    
    for root, _, files in os.walk(inp):
        if not any(f.lower().endswith('.hdr') for f in files):
            continue
        
        # Get white reference file and token (uses actual sensor_type)
        wr_hdr, wr_raw, token = get_white_reference_for_hsi(root, wr_dir, sensor_type)
        if not (wr_hdr and wr_raw):
            print(f"Skipping folder due to missing white reference: {root}")
            continue
        
        # Get panel definition file (ALWAYS uses "SWIR" regardless of actual sensor_type)
        panel_xlsx = get_reference_panel_definition(wr_dir, token, "SWIR")
        if not panel_xlsx:
            print(f"Skipping folder due to missing reference panel definition: {root}")
            continue
        
        temp_files = {wr_hdr, wr_raw, panel_xlsx}
        
        try:
            # Load white reference data
            wdata, wmeta = load_envi_data(wr_hdr, wr_raw)
            wdata = wdata.mean(axis=0, keepdims=True)
            
            # Load panel reflectance data
            panel_nm, panel_ref = load_panel_reflectance(panel_xlsx)
            
            # Calibrate white reference
            calib_white = calibrate_white_reference(wdata, wmeta, panel_nm, panel_ref)
            
            # Create output directory
            rel_path = os.path.relpath(root, inp)
            tgt_dir = os.path.join(outp, rel_path)
            os.makedirs(tgt_dir, exist_ok=True)
            
            files_processed = False
            
            # Process each HSI file
            for f in files:
                if f.lower().endswith('.hdr') and '_cor' not in f.lower():
                    hdr_path = os.path.join(root, f)
                    base = os.path.splitext(f)[0]
                    raw_path = os.path.join(root, base + ".raw")
                    
                    if not os.path.exists(raw_path):
                        continue
                    
                    try:
                        # Load raw HSI data
                        raw_data, raw_meta = load_envi_data(hdr_path, raw_path)
                        
                        # Apply reflectance correction
                        refl = correct_raw_hsi_with_calibrated_wh(calib_white, raw_data)
                        
                        # Update metadata and save
                        new_meta = update_metadata(raw_meta)
                        out_hdr, out_raw = get_output_filenames(hdr_path, tgt_dir)
                        os.makedirs(os.path.dirname(out_hdr), exist_ok=True)
                        envi.save_image(out_hdr, refl, force=True,
                                      interleave=new_meta["interleave"],
                                      metadata=new_meta, dtype=np.float32)
                        
                        print(f"Processed: {os.path.basename(hdr_path)}")
                        
                        # Remove original files
                        os.remove(hdr_path)
                        os.remove(raw_path)
                        files_processed = True
                    
                    except Exception as e:
                        print(f"Error processing {os.path.basename(hdr_path)}: {e}")
            
            if files_processed:
                used_files.update(temp_files)
                
        except Exception as e:
            print(f"Error processing folder: {e}")
    
    return used_files

def cleanup_empty_folders(directory):
    """Remove empty directories after processing"""
    for root, dirs, _ in os.walk(directory, topdown=False):
        for d in dirs:
            dp = os.path.join(root, d)
            if not os.listdir(dp):
                os.rmdir(dp)
                print(f"Removed empty directory: {os.path.basename(dp)}")


def delete_files(paths):
    """Delete files with error handling"""
    for p in paths:
        try:
            os.remove(p)
            print(f"Deleted used file: {os.path.basename(p)}")
        except Exception as e:
            print(f"Failed to delete {os.path.basename(p)}: {e}")
# ─────────────────────────────────────────────────────────────────────────────


def reflect_correct_hsi(folder_path, log_widget):
    """GUI callback — reads widget values, then delegates to processing functions."""
    base_folder = folder_path.strip()
    if not base_folder or not os.path.isdir(base_folder):
        messagebox.showerror("Error", "Please provide a valid ANCPRJ folder path.")
        return

    swir_input    = os.path.join(base_folder, "SWIR_HSI_Files")
    vnir_input    = os.path.join(base_folder, "VNIR_HSI_Files")
    white_ref_dir = os.path.join(base_folder, "Extracted_WR")

    missing = [os.path.basename(d) for d in [swir_input, vnir_input, white_ref_dir]
               if not os.path.isdir(d)]
    if missing:
        messagebox.showerror("Error", f"Missing required folders: {', '.join(missing)}")
        return

    corrected_swir = os.path.join(base_folder, "Corrected_SWIR")
    corrected_vnir = os.path.join(base_folder, "Corrected_VNIR")
    os.makedirs(corrected_swir, exist_ok=True)
    os.makedirs(corrected_vnir, exist_ok=True)

    old_stdout = sys.stdout
    sys.stdout = TextRedirector(log_widget, "stdout")
    try:
        print("Starting Reflectance Correction for SWIR...")
        used_swir = process_directory_with_calib(swir_input, corrected_swir, white_ref_dir, "SWIR")
        cleanup_empty_folders(swir_input)
        print("Completed SWIR reflectance correction.")

        print("Starting Reflectance Correction for VNIR...")
        used_vnir = process_directory_with_calib(vnir_input, corrected_vnir, white_ref_dir, "VNIR")
        cleanup_empty_folders(vnir_input)
        print("Completed VNIR reflectance correction.")

        delete_files(used_swir)
        delete_files(used_vnir)
        messagebox.showinfo("Success", "Reflectance correction completed successfully.")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")
    finally:
        sys.stdout = old_stdout
