"""
depth_overlap.py – CODE 7: Make Depth Overlap Corrections
Detects and fixes depth overlaps across core boxes in XML and HDR files.
"""
import os, sys, re
import xml.etree.ElementTree as ET
from tkinter import messagebox
from pathlib import Path

from utils import open_with_buffer, TextRedirector


def parse_corebox_info_overlap(xml_path):
    """Extract CoreBox number and depth information from XML"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Get CoreBox number
        corebox_elem = root.find('.//CoreBox')
        if corebox_elem is None:
            print(f"Warning: No CoreBox found in {xml_path}")
            return None
        
        corebox_num = int(corebox_elem.text)
        
        # Get measurement ID
        measurement_id_elem = root.find('.//measurement/id')
        measurement_id = None
        if measurement_id_elem is not None:
            measurement_id = measurement_id_elem.text.strip('{}')
        
        # Get HSI results
        hsi_results = root.find('.//HSIresults')
        if hsi_results is None:
            print(f"Warning: No HSIresults in {xml_path}")
            return None
        
        hsi_pieces = []
        for hsi in hsi_results.findall('HSIresult'):
            start_elem = hsi.find('startTime/position')
            stop_elem = hsi.find('stopTime/position')
            if start_elem is not None and stop_elem is not None:
                start_pos = float(start_elem.text)
                stop_pos = float(stop_elem.text)
                hsi_pieces.append((start_pos, stop_pos))
        
        if not hsi_pieces:
            print(f"Warning: No HSI pieces found in {xml_path}")
            return None
        
        # Sort pieces by start position
        hsi_pieces.sort(key=lambda x: x[0])
        
        return {
            'path': xml_path,
            'corebox': corebox_num,
            'measurement_id': measurement_id,
            'first_start': hsi_pieces[0][0],
            'last_stop': hsi_pieces[-1][1],
            'pieces': hsi_pieces
        }
        
    except Exception as e:
        print(f"Error parsing {xml_path}: {e}")
        return None

def sort_hsi_results_in_xml_overlap(xml_path):
    """Sort HSI and VNIR results by start position within the XML"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        modified = False
        
        # Sort HSIresults
        hsi_results = root.find('.//HSIresults')
        if hsi_results is not None:
            hsi_list = list(hsi_results.findall('HSIresult'))
            if len(hsi_list) > 1:
                hsi_with_pos = []
                for hsi in hsi_list:
                    start_elem = hsi.find('startTime/position')
                    if start_elem is not None:
                        pos = float(start_elem.text)
                        hsi_with_pos.append((pos, hsi))
                
                hsi_with_pos.sort(key=lambda x: x[0])
                
                original_order = [float(hsi.find('startTime/position').text) for hsi in hsi_list if hsi.find('startTime/position') is not None]
                sorted_order = [x[0] for x in hsi_with_pos]
                
                if original_order != sorted_order:
                    for hsi in hsi_list:
                        hsi_results.remove(hsi)
                    for _, hsi in hsi_with_pos:
                        hsi_results.append(hsi)
                    modified = True
                    print(f"  Sorted HSIresults: {original_order} -> {sorted_order}")
        
        # Sort VNIRresults
        vnir_results = root.find('.//VNIRresults')
        if vnir_results is not None:
            vnir_list = list(vnir_results.findall('HSIresult'))
            if len(vnir_list) > 1:
                vnir_with_pos = []
                for vnir in vnir_list:
                    start_elem = vnir.find('startTime/position')
                    if start_elem is not None:
                        pos = float(start_elem.text)
                        vnir_with_pos.append((pos, vnir))
                
                vnir_with_pos.sort(key=lambda x: x[0])
                
                original_order = [float(vnir.find('startTime/position').text) for vnir in vnir_list if vnir.find('startTime/position') is not None]
                sorted_order = [x[0] for x in vnir_with_pos]
                
                if original_order != sorted_order:
                    for vnir in vnir_list:
                        vnir_results.remove(vnir)
                    for _, vnir in vnir_with_pos:
                        vnir_results.append(vnir)
                    modified = True
                    print(f"  Sorted VNIRresults: {original_order} -> {sorted_order}")
        
        if modified:
            tree.write(xml_path, encoding="utf-8", xml_declaration=True)
            print(f"  Saved sorted results to {os.path.basename(xml_path)}")
        
        return modified
        
    except Exception as e:
        print(f"Error sorting results in {xml_path}: {e}")
        return False

def fix_overlap_depth(xml_path, new_stop_position, old_stop_position):
    """Fix the last piece's stop position in both HSI and VNIR results"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        modified = False
        
        # Fix HSIresults - get last result
        hsi_results = root.find('.//HSIresults')
        if hsi_results is not None:
            hsi_list = list(hsi_results.findall('HSIresult'))
            if hsi_list:
                last_hsi = hsi_list[-1]
                stop_elem = last_hsi.find('stopTime/position')
                if stop_elem is not None:
                    old_stop = float(stop_elem.text)
                    stop_elem.text = f"{new_stop_position:.6f}"
                    print(f"  HSI last piece: stop changed from {old_stop:.6f} to {new_stop_position:.6f}")
                    modified = True
        
        # Fix VNIRresults - get last result
        vnir_results = root.find('.//VNIRresults')
        if vnir_results is not None:
            vnir_list = list(vnir_results.findall('HSIresult'))
            if vnir_list:
                last_vnir = vnir_list[-1]
                stop_elem = last_vnir.find('stopTime/position')
                if stop_elem is not None:
                    old_stop = float(stop_elem.text)
                    stop_elem.text = f"{new_stop_position:.6f}"
                    print(f"  VNIR last piece: stop changed from {old_stop:.6f} to {new_stop_position:.6f}")
                    modified = True
        
        if modified:
            tree.write(xml_path, encoding="utf-8", xml_declaration=True)
            print(f"  ✓ Saved changes to {os.path.basename(xml_path)}")
            return True, old_stop_position
        else:
            print(f"  Warning: No changes made to {os.path.basename(xml_path)}")
            return False, None
            
    except Exception as e:
        print(f"Error fixing overlap in {xml_path}: {e}")
        return False, None

def update_hdr_file_overlap(hdr_path, old_start, old_stop, new_start, new_stop):
    """Update Depth From and Depth To in .hdr file"""
    try:
        with open(hdr_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update Depth From
        content = re.sub(
            r'Depth From\s*=\s*[0-9.+-]+',
            f'Depth From = {new_start:.6f}',
            content,
            flags=re.IGNORECASE
        )
        
        # Update Depth To
        content = re.sub(
            r'Depth To\s*=\s*[0-9.+-]+',
            f'Depth To = {new_stop:.6f}',
            content,
            flags=re.IGNORECASE
        )
        
        with open(hdr_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"    Updated .hdr: {old_start:.6f}-{old_stop:.6f} -> {new_start:.6f}-{new_stop:.6f}")
        return True
        
    except Exception as e:
        print(f"    Error updating .hdr file {hdr_path}: {e}")
        return False

def rename_hsi_files_overlap(hsi_base_dir, measurement_id, old_stop, new_stop):
    """Rename HSI files and update .hdr content when depth changes"""
    try:
        hsi_path = Path(hsi_base_dir)
        if not hsi_path.exists():
            print(f"  Warning: HSI directory not found: {hsi_base_dir}")
            return False
        
        # Look for folders containing the measurement ID (UUID)
        matching_folders = []
        for folder in hsi_path.iterdir():
            if folder.is_dir() and measurement_id in folder.name:
                matching_folders.append(folder)
        
        if not matching_folders:
            print(f"  Warning: No HSI folders found for measurement ID {measurement_id}")
            return False
        
        print(f"  Found {len(matching_folders)} HSI folder(s) to update")
        
        for folder in matching_folders:
            print(f"  Processing folder: {folder.name}")
            
            # Find files with the old stop position
            old_stop_str = f"{old_stop:.3f}"
            new_stop_str = f"{new_stop:.3f}"
            
            files_to_rename = []
            for file in folder.iterdir():
                if file.suffix.lower() in ['.hdr', '.img']:
                    # Check if filename contains the old stop position
                    match = re.search(r'(\d+\.\d+)_' + re.escape(old_stop_str), file.name)
                    if match:
                        start_pos = float(match.group(1))
                        files_to_rename.append((file, start_pos))
            
            if not files_to_rename:
                print(f"    No files found with stop position {old_stop_str}")
                continue
            
            # Process each file
            for file, start_pos in files_to_rename:
                # Create new filename with updated stop position
                new_filename = file.name.replace(
                    f"{start_pos:.3f}_{old_stop_str}",
                    f"{start_pos:.3f}_{new_stop_str}"
                )
                new_filepath = folder / new_filename
                
                # If it's a .hdr file, update content first
                if file.suffix.lower() == '.hdr':
                    update_hdr_file_overlap(file, start_pos, old_stop, start_pos, new_stop)
                
                # Rename the file
                if file != new_filepath:
                    file.rename(new_filepath)
                    print(f"    Renamed: {file.name} -> {new_filename}")
        
        return True
        
    except Exception as e:
        print(f"  Error renaming HSI files: {e}")
        return False
# ─────────────────────────────────────────────────────────────────────────────


def adjust_depth_overlap(folder_path, xml_path, log_widget):
    """GUI callback — accepts paths as parameters instead of reading from globals."""
    base_folder = folder_path.strip()
    if not base_folder or not os.path.isdir(base_folder):
        messagebox.showerror("Error", "Please provide a valid ANCPRJ folder path.")
        return
    
    # Automatically locate XML and HSI directories
    xml_directory = os.path.join(base_folder, "XML")
    hsi_directory = os.path.join(base_folder, "Masked_Coreg_HSI")
    
    # Validate directories exist
    if not os.path.exists(xml_directory):
        messagebox.showerror("Error", f"XML directory not found: {xml_directory}")
        return
    
    if not os.path.exists(hsi_directory):
        messagebox.showerror("Error", f"Masked_Coreg_HSI directory not found: {hsi_directory}")
        return
    
    xml_path = Path(xml_directory)
    
    old_stdout = sys.stdout
    sys.stdout = TextRedirector(log_widget, "stdout")
    
    try:
        print("DEPTH OVERLAP CORRECTION")
        print(f"\nXML Directory: {xml_directory}")
        print(f"HSI Directory: {hsi_directory}\n")
        
        # Step 1: Parse all XML files
        print("Step 1: Parsing XML files...")
        sys.stdout.flush()
        xml_files = list(xml_path.glob("*.xml"))
        
        corebox_data = []
        for xml_file in xml_files:
            info = parse_corebox_info_overlap(xml_file)
            if info:
                corebox_data.append(info)
        
        if not corebox_data:
            print("No valid XML files found!")
            messagebox.showinfo("Info", "No valid XML files found to process.")
            return
        
        # Sort by CoreBox number
        corebox_data.sort(key=lambda x: x['corebox'])
        
        print(f"\nFound {len(corebox_data)} core boxes:")
        for data in corebox_data:
            print(f"  CoreBox {data['corebox']:2d}: {data['first_start']:.6f} to {data['last_stop']:.6f} ({os.path.basename(data['path'])})")
        sys.stdout.flush()
        
        # Step 2: Sort HSI results within each XML
        print(f"\nStep 2: Sorting HSI/VNIR results within each XML...")
        sys.stdout.flush()
        for data in corebox_data:
            print(f"\nProcessing CoreBox {data['corebox']}:")
            sys.stdout.flush()
            sort_hsi_results_in_xml_overlap(data['path'])
        
        # Re-parse after sorting
        print(f"\nRe-parsing XMLs after sorting...")
        sys.stdout.flush()
        corebox_data = []
        for xml_file in xml_files:
            info = parse_corebox_info_overlap(xml_file)
            if info:
                corebox_data.append(info)
        corebox_data.sort(key=lambda x: x['corebox'])
        
        # Step 3: Check for overlaps
        print("Step 3: Checking for overlaps between consecutive boxes...")
        sys.stdout.flush()
        
        overlaps_found = []
        
        for i in range(len(corebox_data) - 1):
            current_box = corebox_data[i]
            next_box = corebox_data[i + 1]
            
            current_end = current_box['last_stop']
            next_start = next_box['first_start']
            
            print(f"\nCoreBox {current_box['corebox']} -> CoreBox {next_box['corebox']}:")
            print(f"  Box {current_box['corebox']} ends at:   {current_end:.6f}")
            print(f"  Box {next_box['corebox']} starts at: {next_start:.6f}")
            sys.stdout.flush()
            
            if current_end > next_start:
                overlap = current_end - next_start
                print(f"  ⚠ OVERLAP DETECTED: {overlap:.6f} meters")
                sys.stdout.flush()
                overlaps_found.append({
                    'current': current_box,
                    'next': next_box,
                    'overlap': overlap
                })
            else:
                gap = next_start - current_end
                print(f"  ✓ OK (gap: {gap:.6f} meters)")
                sys.stdout.flush()
        
        # Step 4: Fix overlaps
        if overlaps_found:
            print(f"Step 4: Fixing {len(overlaps_found)} overlap(s)...")
            sys.stdout.flush()
            
            for overlap_info in overlaps_found:
                current_box = overlap_info['current']
                next_box = overlap_info['next']
                new_stop = next_box['first_start']
                old_stop = current_box['last_stop']
                
                print(f"\nFixing CoreBox {current_box['corebox']}:")
                print(f"  Old stop: {old_stop:.6f}")
                print(f"  New stop: {new_stop:.6f}")
                sys.stdout.flush()
                
                success, actual_old_stop = fix_overlap_depth(current_box['path'], new_stop, old_stop)
                
                if success and current_box['measurement_id']:
                    # Update HSI files using only the UUID
                    rename_hsi_files_overlap(hsi_directory, current_box['measurement_id'], 
                                   old_stop, new_stop)
        else:
            print("No overlaps found! All core boxes are properly aligned.")
            sys.stdout.flush()
        
        print("PROCESSING COMPLETE!")
        
        sys.stdout.flush()
        
        messagebox.showinfo("Success", f"Depth overlap correction completed.\n{len(overlaps_found)} overlaps fixed.")
    
    except Exception as e:
        error_msg = f"An error occurred during depth overlap correction:\n{str(e)}"
        print(error_msg)
        sys.stdout.flush()
        messagebox.showerror("Error", error_msg)
    
    finally:
        sys.stdout = old_stdout
