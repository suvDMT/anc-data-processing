"""
xrf_processing.py – CODE 5: XRF Data Processing
Parses, combines, calibrates and exports XRF XML data to Excel.
"""
import os, sys, re, math, random
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET
import openpyxl
from openpyxl.styles import Color
from openpyxl.formatting.rule import DataBarRule
from tkinter import messagebox

from utils import TextRedirector


SHORT_LABEL_MAP = {
    "Zr Ka": "Zirconium - b'K' b'a'",
    "Zn Kb": "Zinc - b'K' b'b'",
    "Zn Ka": "Zinc - b'K' b'a'",
    "Y Kb": "Yttrium - b'K' b'b'",
    "Y Ka": "Yttrium - b'K' b'a'",
    "Xe Lb": "Xenon - b'L' b'b'",
    "Xe La": "Xenon - b'L' b'a'",
    "W Lb": "Tungsten - b'L' b'b'",
    "W La": "Tungsten - b'L' b'a'",
    "V Kb": "Vanadium - b'K' b'b'",
    "V Ka": "Vanadium - b'K' b'a'",
    "Tl Lb": "Thallium - b'L' b'b'",
    "Ti Kb": "Titanum - b'K' b'b'",
    "Ti Ka": "Titanum - b'K' b'a'",
    "Te Ka": "Tellurium - b'K' b'a'",
    "Ta Lb": "Tantalum - b'L' b'b'",
    "Ta La": "Tantalum - b'L' b'a'",
    "Sr Kb": "Strontium - b'K' b'b'",
    "Sr Ka": "Strontium - b'K' b'a'",
    "Sn Kb": "Tin - b'K' b'b'",
    "Sn Ka": "Tin - b'K' b'a'",
    "Si Ka": "Silicon - b'K' b'a'",
    "Se Kb": "Selenium - b'K' b'b'",
    "Se Ka": "Selenium - b'K' b'a'",
    "Sc Kb": "Scandium - b'K' b'b'",
    "Sc Ka": "Scandium - b'K' b'a'",
    "Sb Kb": "Antimony - b'K' b'b'",
    "Sb Ka": "Antimony - b'K' b'a'",
    "S Kb": "Sulfur - b'K' b'b'",
    "S Ka": "Sulfur - b'K' b'a'",
    "Rh Kb": "Rhodium - b'K' b'b'",
    "Rh Ka": "Rhodium - b'K' b'a'",
    "Re Lb": "Rhenium - b'L' b'b'",
    "Re La": "Rhenium - b'L' b'a'",
    "Pt Lb": "Platinum - b'L' b'b'",
    "Pt La": "Platinum - b'L' b'a'",
    "Pd Kb": "Palladium - b'K' b'b'",
    "Pd Ka": "Palladium - b'K' b'a'",
    "Pb Lb": "Lead - b'L' b'b'",
    "Pb La": "Lead - b'L' b'a'",
    "Os Lb": "Osmium - b'L' b'b'",
    "Os La": "Osmium - b'L' b'a'",
    "Ni Kb": "Nickel - b'K' b'b'",
    "Ni Ka": "Nickel - b'K' b'a'",
    "Nb Kb": "Niobium - b'K' b'b'",
    "Nb Ka": "Niobium - b'K' b'a'",
    "Mo Kb": "Molybdenium - b'K' b'b'",
    "Mo Ka": "Molybdenium - b'K' b'a'",
    "Mn Kb": "Manganese - b'K' b'b'",
    "Mn Ka": "Manganese - b'K' b'a'",
    "Mg Ka": "Magnesium - b'K' b'a'",
    "Kr Kb": "Krypton - b'K' b'b'",
    "Kr Ka": "Krypton - b'K' b'a'",
    "K Ka": "Potash - b'K' b'a'",
    "Ir Lb": "Iridium - b'L' b'b'",
    "Ir La": "Iridium - b'L' b'a'",
    "In Kb": "Indium - b'K' b'b'",
    "In Ka": "Indium - b'K' b'a'",
    "Hg Lb": "Mercury - b'L' b'b'",
    "Hg La": "Mercury - b'L' b'a'",
    "Ga Kb": "Gallium - b'K' b'b'",
    "Ga Ka": "Gallium - b'K' b'a'",
    "Fe Kb": "Iron - b'K' b'b'",
    "Fe Ka": "Iron - b'K' b'a'",
    "Cu Kb": "Copper - b'K' b'b'",
    "Cu Ka": "Copper - b'K' b'a'",
    "Cr Kb": "Chromium - b'K' b'b'",
    "Cr Ka": "Chromium - b'K' b'a'",
    "Co Kb": "Cobalt - b'K' b'b'",
    "Co Ka": "Cobalt - b'K' b'a'",
    "Cd Ka": "Cadmium - b'K' b'a'",
    "Ca Kb": "Calcium - b'K' b'b'",
    "Ca Ka": "Calcium - b'K' b'a'",
    "Br Kb": "Bromine - b'K' b'b'",
    "Br Ka": "Bromine - b'K' b'a'",
    "As Kb": "Arsenic - b'K' b'b'",
    "As Ka": "Arsenic - b'K' b'a'",
    "Al Ka": "Aluminum - b'K' b'a'",
    "Ag Ka": "Silver - b'K' b'a'",
}

def _safe_find_text(parent, tag, default=''):
    """Helper function to safely find text from an XML element."""
    if parent is None:
        return default
    f = parent.find(tag) if isinstance(tag, str) else parent
    if f is not None and f.text:
        return f.text.strip()
    return default

def _parse_spectrum_results(sp):
    """
    Returns a dict of short_label -> float(value) from <spectrumResult> blocks.
    """
    d = {}
    sr = sp.find('spectrumResults')
    if sr is None:
        return d
    for x in sr.findall('spectrumResult'):
        target_raw = _safe_find_text(x, 'target', '')
        val_str = _safe_find_text(x, 'value', '0')
        try:
            val = float(val_str)
        except:
            val = 0.0

        short_label = target_raw.split('/')[0].strip()  # e.g. "Pt La / cps" -> "Pt La"
        d[short_label] = val

    return d

def parse_xml(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    company = _safe_find_text(root, './/Company')
    location = _safe_find_text(root, './/Location')
    wellid = _safe_find_text(root, './/WellID')

    # The main XRF results block
    xrfresults = root.find('.//XRFresults')
    if xrfresults is None:
        return pd.DataFrame(), wellid

    xrfresult_list = xrfresults.findall('XrfResult')
    if not xrfresult_list:
        return pd.DataFrame(), wellid

    rows = []

    for xr in xrfresult_list:
        line_id = _safe_find_text(xr, 'lineId')
        meas_id = _safe_find_text(xr, 'measurementId')

        start_pos = float(_safe_find_text(xr.find('./startTime'), 'position', '0'))
        stop_pos  = float(_safe_find_text(xr.find('./stopTime'), 'position', '0'))
        dist = stop_pos - start_pos   # total distance for this block

        spectra_el = xr.find('spectra')
        if spectra_el is None:
            continue

        # Collect all <spectrum>, sort by <timeStart> to ensure chronological
        spectra_list = []
        for s in spectra_el.findall('spectrum'):
            t_start_str = _safe_find_text(s, 'timeStart', '')
            spectra_list.append((s, t_start_str))

        spectra_list.sort(key=lambda x: x[1])  # lexical sort
        n_spectra = len(spectra_list)
        if n_spectra == 0:
            continue

        # Calculate equal depth increment for each spectrum
        depth_increment = dist / n_spectra if n_spectra > 0 else 0

        for i, (spectrum_el, _) in enumerate(spectra_list):
            # Equal distribution of depths
            d_from = start_pos + (i * depth_increment)
            d_to = start_pos + ((i + 1) * depth_increment)
            
            # Ensure last spectrum exactly reaches stop_pos to avoid rounding errors
            if i == n_spectra - 1:
                d_to = stop_pos

            interval_length = d_to - d_from

            row_data = {
                'Company': company,
                'Location': location,
                'WellID': wellid,
                'Measurement ID': meas_id,
                'Line ID': line_id,
                'Depth From': d_from,
                'Depth To':   d_to
            }

            # Mark '!' if zero-length interval
            if interval_length == 0:
                row_data['WellID'] += '!'
            else:
                # Mark '*' if acquisition time is less than 10 seconds
                # Look for timeAcquisition element in the spectrum
                time_acq_str = _safe_find_text(spectrum_el, 'timeAcquisition', '0')
                try:
                    time_acquisition = float(time_acq_str)
                    if time_acquisition < 10:
                        row_data['WellID'] += '*'
                except ValueError:
                    # If we can't parse the time acquisition, don't add the mark
                    pass

            # parse intensities for this spectrum
            spec_map = _parse_spectrum_results(spectrum_el)
            for short_label, val in spec_map.items():
                if short_label in SHORT_LABEL_MAP:
                    row_data[SHORT_LABEL_MAP[short_label]] = val

            rows.append(row_data)

    if not rows:
        return pd.DataFrame(), wellid

    df = pd.DataFrame(rows)
    base_cols = ['Company','Location','WellID','Measurement ID','Line ID','Depth From','Depth To']
    extra_cols = [c for c in df.columns if c not in base_cols]
    extra_cols.sort()
    df = df.reindex(columns=base_cols + extra_cols)
    return df, wellid

def clean_and_combine_xml_data(xml_dir, output_file, required_columns):
    frames = []
    wellids = set()
    
    for f in os.listdir(xml_dir):
        if f.lower().endswith('.xml'):
            path = os.path.join(xml_dir, f)
            df, wellid = parse_xml(path)
            if not df.empty:
                # ensure required_columns exist
                for c in required_columns:
                    if c not in df.columns:
                        df[c] = None
                df = df[required_columns]
                frames.append(df)
                if wellid:
                    wellids.add(wellid)
    
    if not frames:
        combined = pd.DataFrame(columns=required_columns)
    else:
        combined = pd.concat(frames, ignore_index=True)
    
    # Only save to file if output_file is provided
    if output_file:
        # Check if output file exists and append if it does
        if os.path.exists(output_file):
            existing_df = pd.read_excel(output_file)
            combined = pd.concat([existing_df, combined], ignore_index=True)
            # Remove potential duplicates
            combined = combined.drop_duplicates(subset=['WellID', 'Measurement ID', 'Line ID', 'Depth From', 'Depth To'])
        
        combined.to_excel(output_file, index=False)
    
    # Return the combined DataFrame and a representative wellid
    representative_wellid = next(iter(wellids)) if wellids else "Unknown"
    return combined, representative_wellid

def reorder_columns(output_file, required_columns):
    df = pd.read_excel(output_file)
    # Only select columns that exist in the DataFrame
    existing_columns = [col for col in required_columns if col in df.columns]
    df = df[existing_columns]
    if 'Depth From' in df.columns:
        df = df.sort_values('Depth From')
    df.to_excel(output_file, index=False)
    return df

def apply_data_bars(file_path):
    df = pd.read_excel(file_path)
    wb = openpyxl.load_workbook(file_path)
    ws = wb.active
    start_col = 7
    end_col = df.shape[1]
    col_list = df.columns[start_col:end_col]
    color_map = {}

    for c in col_list:
        base = c.split(' - ')[0]
        if base not in color_map:
            color_map[base] = _rand_hex()

    for i, c in enumerate(col_list, start=start_col + 1):
        vals = df[c].dropna()
        if vals.empty:
            continue
        mn, mx = vals.min(), vals.max()
        if mn == mx:
            continue
        base = c.split(' - ')[0]
        color = color_map[base]
        rule = DataBarRule(
            start_type='num', start_value=mn,
            end_type='num', end_value=mx,
            color=Color(rgb=color),
            showValue="None"
        )
        letter = openpyxl.utils.get_column_letter(i)
        ws.conditional_formatting.add(f"{letter}2:{letter}{ws.max_row}", rule)

    wb.save(file_path)

def _rand_hex():
    return ''.join(f"{random.randint(0,255):02X}" for _ in range(3))

name_normalization = {
    "sulphur": "sulphur", "sulfur": "sulphur",
    "molybdenum": "molybdenum", "molybdenium": "molybdenum",
    "aluminium": "aluminum", "aluminum": "aluminum",
    "caesium": "cesium", "cesium": "cesium", "titanium": "titanum",
}

def parse_calib_file(calib_fp):
    with open(calib_fp, 'r') as f:
        lines = [l.strip() for l in f if l.strip()]
    return [(lines[i], lines[i+1]) for i in range(0, len(lines), 2)]

def process_formula(formula):
    if '=' in formula:
        formula = formula.split('=',1)[1].strip()
    formula = re.sub(r'(\d)\(', r'\1*(', formula)
    formula = formula.replace('×','*')
    formula = re.sub(r'10\^−?(\d+)', r'10**(-\1)', formula)
    formula = re.sub(r'10\^(\d+)', r'10**(\1)', formula)
    return formula

def safe_var(name):
    return re.sub(r'\W+', '_', name)

def map_var_to_col(var_text):
    m = re.match(r'([\w\s]+)\s*([KL][ABab])', var_text, re.IGNORECASE)
    if not m:
        return var_text
    elem, suffix = m.group(1).strip(), m.group(2).upper()
    norm = name_normalization.get(elem.lower(), elem.lower())
    return f"{norm.title()} - b'{suffix[0]}' b'{suffix[1].lower()}'"

def build_formula_expr(formula):
    var_map = {}
    pattern = re.compile(r'([A-Za-z]+(?:\s+[A-Za-z]+)*\s*[KL][ABab])')
    def repl(m):
        vt = m.group(1).strip()
        col = map_var_to_col(vt)
        safe = safe_var(col)
        var_map[vt] = {"safe": safe, "excel": col}
        return safe
    proc = pattern.sub(repl, formula)
    return proc, var_map

def fallback_brit_am(row, col):
    m = re.match(r'([A-Za-z]+)\s*-\s*b\'[KL]\'\s*b\'[ab]\'', col)
    if not m:
        return None
    elem = m.group(1)
    for key, canon in name_normalization.items():
        if canon.title() == elem:
            alt = col.replace(elem, key.title(), 1)
            val = row.get(alt, None)
            if val is not None:
                return val
    return None

def fallback_k_l(row, col):
    m = re.match(r'(.*b\')[KL](\' b\'[ab]\')', col)
    if not m:
        return None
    alt = col.replace("K", "L", 1) if "K" in col else col.replace("L", "K", 1)
    return row.get(alt, None)

def eval_calibration(df, new_col, expr, var_map):
    def row_eval(row):
        loc = {}
        for orig, info in var_map.items():
            col = info["excel"]
            val = row.get(col, None)
            if val is None:
                val = fallback_brit_am(row, col)
            if val is None:
                val = fallback_k_l(row, col)
            try:
                val = float(val)
            except (ValueError, TypeError):
                val = 0
            loc[info["safe"]] = val
        try:
            return eval(expr, {"__builtins__": None}, loc)
        except Exception:
            return None
    df[new_col] = df.apply(row_eval, axis=1)

def process_calibrated_file(xrf_file, calib_file, output_file):
    """Process XRF file with calibration formulas, preserve original with additions"""
    if not os.path.exists(xrf_file) or not os.path.exists(calib_file):
        print(f"Error: Missing input files - XRF: {xrf_file}, Calibration: {calib_file}")
        return None
        
    # Check if output file already exists and load it if so
    if os.path.exists(output_file):
        df = pd.read_excel(output_file)
        print(f"Updating existing calibrated file: {output_file}")
    else:
        df = pd.read_excel(xrf_file)
        print(f"Creating new calibrated file: {output_file}")
    
    if "Depth To" not in df.columns:
        print("Error: 'Depth To' column not found in XRF file")
        return None
    
    # Remove '*' marker from WellID for calibrated file
    if 'WellID' in df.columns:
        df['WellID'] = df['WellID'].astype(str).str.replace('*', '', regex=False)
    
    # Load and apply calibrations
    calib_entries = parse_calib_file(calib_file)
    print(f"Found {len(calib_entries)} calibration formulas")
    
    # Keep track of calibration column names
    calibration_columns = []
    
    # Apply each calibration formula to the DataFrame
    for new_col, formula_line in calib_entries:
        print(f"Processing calibration: {new_col}")
        expr_clean = process_formula(formula_line)
        expr, var_map = build_formula_expr(expr_clean)
        eval_calibration(df, new_col, expr, var_map)
        calibration_columns.append(new_col)
    
    # Replace negative values with 0 in calibration columns
    for col in calibration_columns:
        if col in df.columns:
            # Replace negative values with 0, preserve NaN/None values
            df[col] = df[col].apply(lambda x: 0 if pd.notnull(x) and x < 0 else x)
            negative_count = (df[col] < 0).sum()
            if negative_count > 0:
                print(f"Replaced {negative_count} negative values with 0 in column: {col}")
    
    # Reorder columns: base columns + calibration columns + remaining columns
    base_cols = ['Company', 'Location', 'WellID', 'Measurement ID', 'Line ID', 'Depth From', 'Depth To']
    
    # Get existing calibration columns that are actually in the dataframe
    existing_calib_cols = [col for col in calibration_columns if col in df.columns]
    
    # Get all remaining columns (original XRF intensity columns)
    remaining_cols = [col for col in df.columns if col not in base_cols and col not in existing_calib_cols]
    
    # Reorder the dataframe
    final_column_order = base_cols + existing_calib_cols + remaining_cols
    df = df[final_column_order]
    
    # Save the updated DataFrame
    df.to_excel(output_file, index=False)
    print(f"Saved calibrated data to: {output_file}")
    
    # Apply data bars to the calibrated file
    apply_data_bars(output_file)
    
    return output_file

def run_main(base_folder, xml_path, calib_path):
    # Determine XML source directory and output directory
    if xml_path and os.path.exists(xml_path):
        if os.path.isdir(xml_path):
            xml_dir = xml_path
        else:
            xml_dir = os.path.dirname(xml_path)
        # Create output directory within the XML directory
        output_dir = os.path.join(xml_dir, "Output")
    else:
        # Fallback to XML folder within base_folder
        xml_dir = os.path.join(base_folder, "XML")
        if not os.path.exists(xml_dir):
            messagebox.showerror("Error", "No XML files found. Please provide a valid XML path.")
            return
        # Create output directory within the base folder
        output_dir = os.path.join(base_folder, "Output")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Using XML files from: {xml_dir}")
    print(f"Output files will be saved to: {output_dir}")
    
    # Define required columns - if new elements added have to be updated in the list
    req_cols = [
        'Company', 'Location', 'WellID', 'Measurement ID', 'Line ID', 'Depth From', 'Depth To',
        "Magnesium - b'K' b'a'", "Aluminum - b'K' b'a'", "Silicon - b'K' b'a'", "Phosphorus - b'K' b'a'",
        "Sulfur - b'K' b'a'", "Chlorine - b'K' b'a'", "Argon - b'K' b'a'", "Potash - b'K' b'a'", "Potash - b'K' b'b'",
        "Calcium - b'K' b'a'", "Calcium - b'K' b'b'", "Scandium - b'K' b'a'", "Scandium - b'K' b'b'",
        "Titanum - b'K' b'a'", "Titanum - b'K' b'b'", "Vanadium - b'K' b'a'", "Vanadium - b'K' b'b'",
        "Chromium - b'K' b'a'", "Chromium - b'K' b'b'", "Manganese - b'K' b'a'", "Manganese - b'K' b'b'",
        "Iron - b'K' b'a'", "Iron - b'K' b'b'", "Cobalt - b'K' b'a'", "Cobalt - b'K' b'b'", "Nickel - b'K' b'a'",
        "Nickel - b'K' b'b'", "Copper - b'K' b'a'", "Copper - b'K' b'b'", "Zinc - b'K' b'a'", "Zinc - b'K' b'b'",
        "Gallium - b'K' b'a'", "Gallium - b'K' b'b'", "Germanium - b'K' b'a'", "Germanium - b'K' b'b'",
        "Arsenic - b'K' b'a'", "Arsenic - b'K' b'b'", "Selenium - b'K' b'a'", "Selenium - b'K' b'b'",
        "Bromine - b'K' b'a'", "Bromine - b'K' b'b'", "Krypton - b'K' b'a'", "Krypton - b'K' b'b'",
        "Strontium - b'K' b'a'", "Strontium - b'K' b'b'", "Yttrium - b'K' b'a'", "Yttrium - b'K' b'b'",
        "Zirconium - b'K' b'a'", "Zirconium - b'K' b'b'", "Niobium - b'K' b'a'", "Niobium - b'K' b'b'",
        "Molybdenium - b'K' b'a'", "Molybdenium - b'K' b'b'", "Rhodium - b'K' b'a'", "Rhodium - b'K' b'b'",
        "Palladium - b'K' b'a'", "Palladium - b'K' b'b'", "Silver - b'K' b'a'", "Silver - b'K' b'b'",
        "Cadmium - b'K' b'a'", "Cadmium - b'K' b'b'", "Indium - b'K' b'a'", "Indium - b'K' b'b'",
        "Tin - b'K' b'a'", "Tin - b'K' b'b'", "Antimony - b'K' b'a'", "Antimony - b'K' b'b'",
        "Tellurium - b'K' b'a'", "Tellurium - b'K' b'b'", "Iodine - b'L' b'a'", "Iodine - b'L' b'b'",
        "Xenon - b'L' b'a'", "Xenon - b'L' b'b'", "Tantalum - b'L' b'a'", "Tantalum - b'L' b'b'",
        "Tungsten - b'L' b'a'", "Tungsten - b'L' b'b'", "Rhenium - b'L' b'a'", "Rhenium - b'L' b'b'",
        "Osmium - b'L' b'a'", "Osmium - b'L' b'b'", "Iridium - b'L' b'a'", "Iridium - b'L' b'b'",
        "Platinum - b'L' b'a'", "Platinum - b'L' b'b'", "Platin - b'L' b'a'", "Platin - b'L' b'b'",
        "Mercury - b'L' b'a'", "Mercury - b'L' b'b'", "Thallium - b'L' b'a'", "Thallium - b'L' b'b'",
        "Lead - b'L' b'a'", "Lead - b'L' b'b'", "Silicon - b'K' b'b'", "Sulfur - b'K' b'b'",
        "Sodium - b'K' b'a'"
    ]
    
    # Process XML files directly to the wellid-based filename
    print("Processing XML files and generating XRF data...")
    
    # Get combined data and wellid, without creating any intermediate file  
    frames = []
    wellids = set()
    
    # Go through all XML files
    for f in os.listdir(xml_dir):
        if f.lower().endswith('.xml'):
            path = os.path.join(xml_dir, f)
            df, wellid = parse_xml(path)
            if not df.empty:
                # Ensure required columns
                for c in req_cols:
                    if c not in df.columns:
                        df[c] = None
                df = df[req_cols]
                frames.append(df)
                if wellid:
                    wellids.add(wellid)

    # Combine all parsed frames
    if not frames:
        combined_df = pd.DataFrame(columns=req_cols)
        wellid = "OutputSample"  # fallback if NO data found
    else:
        combined_df = pd.concat(frames, ignore_index=True)
        if 'Depth From' in combined_df.columns:
            combined_df = combined_df.sort_values('Depth From')
        wellid = next(iter(wellids)) if wellids else "OutputSample"  # fallback if no wellid

    # Clean and validate wellid
    if not wellid or wellid.strip().lower() in ["", "unknown", "unknownwell", "none"]:
        wellid = "OutputSample"
    else:
        wellid = wellid.replace(" ", "_").replace(".", "_")
    
    # Create the base XRF Excel file with the wellid in the name
    base_xrf_file = os.path.join(output_dir, f"XRF_data_{wellid}.xlsx")
    
    # Check if the file already exists
    if os.path.exists(base_xrf_file):
        existing_df = pd.read_excel(base_xrf_file)
        combined_df = pd.concat([existing_df, combined_df], ignore_index=True)
        # Remove potential duplicates
        combined_df = combined_df.drop_duplicates(subset=['WellID', 'Measurement ID', 'Line ID', 'Depth From', 'Depth To'])
    
    # Save directly to the wellid file
    combined_df.to_excel(base_xrf_file, index=False)
    
    # Apply data bars to the base file
    apply_data_bars(base_xrf_file)
    print(f"Base XRF data file created: {base_xrf_file}")
    
    # Apply calibration if a calibration file is provided
    if calib_path and os.path.exists(calib_path):
        print(f"Applying calibration from: {calib_path}")
        calibrated_file = os.path.join(output_dir, f"XRF_Data_Calibrated_{wellid}.xlsx")
        result = process_calibrated_file(base_xrf_file, calib_path, calibrated_file)
        if result:
            print(f"Calibrated XRF file created: {calibrated_file}")
        else:
            print("Calibration process failed.")
    else:
        print("No calibration file provided or file not found. Skipping calibration.")
    
    messagebox.showinfo("Success", f"XRF data processing completed. Files saved to {output_dir}")
    return output_dir
# ─────────────────────────────────────────────────────────────────────────────


def start_processing_xml_combine(folder_path, xml_path, calib_path, log_widget):
    """GUI callback — reads widget values, then delegates to run_main."""
    base_folder = folder_path.strip()
    xp          = xml_path.strip()
    cp          = calib_path.strip()
    if not base_folder or not os.path.isdir(base_folder):
        messagebox.showerror("Error", "Please provide a valid folder path.")
        return
    old_stdout = sys.stdout
    sys.stdout = TextRedirector(log_widget, "stdout")
    try:
        run_main(base_folder, xp, cp)
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")
    finally:
        sys.stdout = old_stdout
