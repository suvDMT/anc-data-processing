"""
coregistration.py – CODE 3: Coregister SWIR-VNIR Corrected Files
Applies an affine transform to align SWIR and VNIR hyperspectral cubes.
"""
import os
import re
import sys
import glob
import time
import inspect

import numpy as np
import spectral.io.envi as envi
from datetime import datetime
from scipy.ndimage import zoom
from skimage.transform import AffineTransform, warp
from tkinter import messagebox

from config import TRANSFORM_PARAMETERS_FILE
from utils import TextRedirector


def coregister_hsi_optimized(folder_path, log_widget):
    """
    GUI callback + full processing logic for SWIR/VNIR coregistration.
    Accepts folder_path (str) and log_widget (tk.Text) instead of reading
    from global Tkinter widget variables.
    """
    base_folder = folder_path.strip()
    if not base_folder or not os.path.isdir(base_folder):
        messagebox.showerror("Error", "Please provide a valid ANCPRJ folder path.")
        return

    swir_dir   = os.path.join(base_folder, "Corrected_SWIR")
    vnir_dir   = os.path.join(base_folder, "Corrected_VNIR")
    output_dir = os.path.join(base_folder, "Coregistered_HSI")

    if not os.path.isdir(swir_dir) or not os.path.isdir(vnir_dir):
        messagebox.showerror("Error", "Corrected_SWIR and/or Corrected_VNIR folders are missing.")
        return

    os.makedirs(output_dir, exist_ok=True)

    # Hardcoded fixed location of transform parameters file
    transform_file = TRANSFORM_PARAMETERS_FILE

    old_stdout = sys.stdout
    sys.stdout = TextRedirector(log_widget, "stdout")

    try:
        print("Starting VNIR/SWIR coregistration...")
        sys.stdout.flush()

        # --Load transform matrix from file -----------
        def load_affine(txt_file):
            try:
                with open(txt_file, 'r') as f:
                    rows = [l for l in f if l.strip() and not l.startswith("#")]
                    mat = np.array([[float(x) for x in r.split()[:3]] for r in rows[:3]])
                    return mat
            except Exception as e:
                raise ValueError(f"Failed to load transform parameters: {e}")
        
        # Load transform matrix
        try:
            transform_matrix = load_affine(transform_file)
            print(f"Using transform matrix:\n{transform_matrix}")
            sys.stdout.flush()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
            
        # helper functions 
        def remove_duplicate_lines_fast(cube, max_top_check=30, similarity=0.999):
            for i in range(min(max_top_check, cube.shape[0] - 1)):
                a, b = cube[i].ravel(), cube[i + 1].ravel()
                if (a @ b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9) < similarity:
                    return i
            return 0

        def resample_image(cube, new_h, new_w):
            z_y, z_x = new_h / cube.shape[0], new_w / cube.shape[1]
            return zoom(cube, (z_y, z_x, 1), order=1)

        def get_wavelengths(meta):
            return np.asarray([float(w) for w in meta.get("wavelength", [])], float)
        
        # Version-proof affine warp 
        _warp_sig = inspect.signature(warp).parameters
        if "channel_axis" in _warp_sig:
            def _warp_cube(cube, tform):
                return warp(cube, tform.inverse, order=1, mode="edge",
                          preserve_range=True, channel_axis=-1).astype(cube.dtype)
        elif "multichannel" in _warp_sig:
            def _warp_cube(cube, tform):
                return warp(cube, tform.inverse, order=1, mode="edge",
                          preserve_range=True, multichannel=True).astype(cube.dtype)
        else:
            def _warp_cube(cube, tform):
                out = np.empty_like(cube)
                for b in range(cube.shape[2]):
                    out[:, :, b] = warp(cube[:, :, b], tform.inverse,
                                      order=1, mode="edge",
                                      preserve_range=True)
                return out
        
        # Fast composite function 
        def create_cross_calibrated_composite_fast(vnir, swir, vnir_wv, swir_wv,
                                                transition_width=5.0):
            vnir, swir = vnir.astype(np.float32), swir.astype(np.float32)
            vnir_wv, swir_wv = map(np.asarray, (vnir_wv, swir_wv))
            ov_min, ov_max = max(vnir_wv[0], swir_wv[0]), min(vnir_wv[-1], swir_wv[-1])
            tr_c = ov_max - transition_width
            tr_s, tr_e = tr_c - transition_width / 2, tr_c + transition_width / 2

            v_only = np.where(vnir_wv < tr_s)[0]
            s_only = np.where(swir_wv > tr_e)[0]
            v_cal  = np.where((vnir_wv >= ov_min) & (vnir_wv <= ov_max))[0]
            s_cal  = np.where((swir_wv >= ov_min) & (swir_wv <= ov_max))[0]

            min_len = min(len(v_cal), len(s_cal))
            if min_len == 0:                       
                scale = np.ones(vnir.shape[:2], np.float32)
            else:
                ratio = np.divide(
                    swir[:, :, s_cal[:min_len]],      
                    vnir[:, :, v_cal[:min_len]],      
                    out=np.full_like(vnir[:, :, v_cal[:min_len]], np.nan),
                    where=vnir[:, :, v_cal[:min_len]] > 1e-2
                )
                scale = np.nanmedian(ratio, axis=-1)
                scale[np.isnan(scale)] = 1.0
            v_scaled = vnir * scale[..., None]

            L, S, _ = swir.shape
            trans_wv = np.linspace(tr_s, tr_e, 5)
            comp = np.empty((L, S, len(v_only) + len(trans_wv) + len(s_only)),
                          dtype=np.float32)

            comp[:, :, :len(v_only)] = v_scaled[:, :, v_only]

            wts = 3*(np.linspace(0,1,5)**2) - 2*(np.linspace(0,1,5)**3)
            for k, w in enumerate(wts):
                i_out = len(v_only)+k
                i_v   = vnir_wv.searchsorted(trans_wv[k])
                i_s   = swir_wv.searchsorted(trans_wv[k])
                comp[:, :, i_out] = (1-w)*v_scaled[:, :, i_v] + w*swir[:, :, i_s]

            comp[:, :, len(v_only)+len(trans_wv):] = swir[:, :, s_only]
            out_wv = np.concatenate([vnir_wv[v_only], trans_wv, swir_wv[s_only]])
            return comp, out_wv.astype(str).tolist()

        # Optimized process_pair function
        def process_pair(swir_hdr, vnir_hdr, out_dir, out_name, tform):
            # Skip if input files are already marked as processed (have _crg suffix)
            if "_crg" in swir_hdr or "_crg" in vnir_hdr:
                return False, "skipped_processed"
                
            # Check if output file already exists
            out_path = os.path.join(out_dir, out_name + ".hdr")
            if os.path.exists(out_path):
                return False, "skipped_exists"
                
            os.makedirs(out_dir, exist_ok=True)
        
            swir_img = envi.open(swir_hdr)
            vnir_img = envi.open(vnir_hdr)
            
            # Load data
            swir = swir_img.load().astype(np.float32)
            vnir = vnir_img.load().astype(np.float32)

            # Process SWIR image
            swir = np.flip(swir, axis=1)
            dup = remove_duplicate_lines_fast(swir)
            if dup > 0:
                swir = swir[dup:]

            # Resample VNIR if needed
            if swir.shape[:2] != vnir.shape[:2]:
                vnir = resample_image(vnir, *swir.shape[:2])

            # Apply transformation
            vnir = _warp_cube(vnir, tform)

            # Create composite
            comp, comp_wv = create_cross_calibrated_composite_fast(
                vnir, swir, 
                get_wavelengths(vnir_img.metadata), 
                get_wavelengths(swir_img.metadata)
            )

            # Update metadata
            meta = swir_img.metadata.copy()
            meta.update(
                bands=len(comp_wv), 
                wavelength=comp_wv,
                **{
                    "acquisition date": datetime.now().strftime("%Y-%m-%d"),
                    "acquisition time": datetime.now().strftime("%H:%M:%S")
                }
            )

            # Save composite (without _crg suffix in output)
            envi.save_image(
                out_path, 
                comp, 
                force=True, 
                dtype=np.float32,
                interleave=meta.get("interleave", "bil"),
                metadata=meta
            )
            
            # Mark the input files as processed by renaming them with _crg suffix
            try:
                # Rename SWIR files (.hdr and corresponding .img)
                swir_base, swir_ext = os.path.splitext(swir_hdr)
                swir_img = swir_base + ".img"
                
                new_swir_hdr = f"{swir_base}_crg{swir_ext}"
                new_swir_img = f"{swir_base}_crg.img"
                
                os.rename(swir_hdr, new_swir_hdr)
                if os.path.exists(swir_img):
                    os.rename(swir_img, new_swir_img)
                
                # Rename VNIR files (.hdr and corresponding .img)
                vnir_base, vnir_ext = os.path.splitext(vnir_hdr)
                vnir_img = vnir_base + ".img"
                
                new_vnir_hdr = f"{vnir_base}_crg{vnir_ext}"
                new_vnir_img = f"{vnir_base}_crg.img"
                
                os.rename(vnir_hdr, new_vnir_hdr)
                if os.path.exists(vnir_img):
                    os.rename(vnir_img, new_vnir_img)
            except Exception as e:
                print(f" - Warning: Could not rename input files: {e}")
            
            return True, "processed"

        # Folder and filename matching from original code
        _depth = re.compile(r'(\d+\.\d+_\d+\.\d+)')
        _guid  = re.compile(r'{([^}]+)}')

        def folder_pairs(root_a, root_b):
            a = {d.split("{")[0]: d for d in os.listdir(root_a) if "{" in d}
            b = {d.split("{")[0]: d for d in os.listdir(root_b) if "{" in d}
            pairs = []
            for k in a.keys() & b.keys():
                guid_a = a[k][a[k].find("{")+1:a[k].find("}")]
                guid_b = b[k][b[k].find("{")+1:b[k].find("}")]
                out_subdir = f"{k}{{{guid_b}}}_{{{guid_a}}}"
                pairs.append((
                    os.path.join(root_a, a[k]),
                    os.path.join(root_b, b[k]),
                    out_subdir
                ))
            return pairs

        def hdr_pairs(dir_a, dir_b):
            # Build lookup dictionary just once
            a_files = glob.glob(os.path.join(dir_a, "*.hdr"))
            A = {}
            for f in a_files:
                m = _depth.search(f)
                if m:
                    A[m.group(1)] = f
            
            # Find matching files
            pairs = []
            for vn in glob.glob(os.path.join(dir_b, "*.hdr")):
                d = _depth.search(vn)
                if not d or d.group(1) not in A:
                    continue
                    
                sw = A[d.group(1)]
                m_sw = _guid.search(sw)
                m_vn = _guid.search(vn)
                
                gid_sw = m_sw.group(1) if m_sw else "unknown"
                gid_vn = m_vn.group(1) if m_vn else "unknown"
                
                name = f"{d.group(1)}_{{{gid_vn}}}_{{{gid_sw}}}"
                pairs.append((sw, vn, name))
            
            return pairs

        # Main processing with optimization
        tform = AffineTransform(matrix=transform_matrix)
        t0 = time.time()
        
        # Use batch reporting instead of per-file
        total = processed = skipped = failed = 0
        skipped_processed = skipped_exists = 0
        
        # Get all folder pairs upfront (avoid generator)
        all_folder_pairs = folder_pairs(swir_dir, vnir_dir)
        
        # Process each folder pair
        for idx, (sw_dir, vn_dir, out_sub) in enumerate(all_folder_pairs):
            folder_name = os.path.basename(sw_dir)
            print(f"Processing folder pair {idx+1}/{len(all_folder_pairs)}: {folder_name}")
            sys.stdout.flush()
            
            # Get all file pairs upfront
            file_pairs = hdr_pairs(sw_dir, vn_dir)
            processed_in_folder = 0
            
            # Process all files in the folder
            for sw_hdr, vn_hdr, name in file_pairs:
                total += 1
                try:
                    result, status = process_pair(sw_hdr, vn_hdr, 
                                      os.path.join(output_dir, out_sub), name, tform)
                    if result:
                        processed += 1
                        processed_in_folder += 1
                    else:
                        skipped += 1
                        if status == "skipped_processed":
                            skipped_processed += 1
                        elif status == "skipped_exists":
                            skipped_exists += 1
                except Exception as e:
                    print(f" - Error processing {os.path.basename(sw_hdr)}: {e}")
                    failed += 1
            
            # Report only after each folder is complete
            if processed_in_folder > 0:
                print(f" - Processed {processed_in_folder} files")
            elif skipped > 0:
                print(f" - All files already processed")
            sys.stdout.flush()
        
        # Final report
        elapsed = time.time() - t0
        print(f"\nFinished coregistration:")
        print(f" - {processed} files processed")
        print(f" - {skipped_processed} files skipped (already processed)")
        print(f" - {skipped_exists} files skipped (output exists)")
        print(f" - {failed} files failed")
        print(f"Total time: {elapsed:.1f}s")
        sys.stdout.flush()
        
        messagebox.showinfo("Success", f"Coregistration completed: {processed} files processed")
    
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred during coregistration:\n{e}")
    
    finally:
        sys.stdout = old_stdout