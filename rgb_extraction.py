"""
rgb_extraction.py – CODE 6: Extract RGB Core Pieces with Enhancement
Crops, enhances, and saves individual core-piece images from RGB scans.
"""
import os, sys, re, math
import cv2
import numpy as np
from PIL import Image
import xml.etree.ElementTree as ET
from tkinter import messagebox

from utils import TextRedirector


def enhance_core_box_image_fast(image):
    """
    Faster enhancement with fewer operations while maintaining quality.
    Same function as in Code 8 for consistency.
    """
    # Method 1: Combined brightness/contrast in one operation
    # Slightly increase contrast and brightness
    enhanced = cv2.addWeighted(image, 1.15, image, 0, 25)
    
    # Method 2: Simple gamma correction using lookup table
    gamma = 0.8
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    enhanced = cv2.LUT(enhanced, table)
    
    return enhanced

def estimate_jpeg_quality_for_size(original_size):
    """
    Estimate JPEG quality based on original file size.
    Same function as in Code 8 for consistency.
    """
    size_mb = original_size / (1024 * 1024)
    
    if size_mb < 2:
        return 80
    elif size_mb < 5:
        return 85
    else:
        return 90
# ─────────────────────────────────────────────────────────────────────────────


def extract_rgb_core_pieces(folder_path, xml_path, log_widget):
    """GUI callback — accepts paths as parameters instead of reading from globals."""
    base_folder = folder_path.strip()
    if not base_folder or not os.path.isdir(base_folder):
        messagebox.showerror("Error", "Please provide a valid ANCPRJ folder path.")
        return

    # Check for XML folder; if empty, fallback to xml_entry
    xml_dir = os.path.join(base_folder, "XML")
    if not os.path.exists(xml_dir) or not os.listdir(xml_dir):
        xml_entry_path = xml_path.strip()
        if not xml_entry_path or not os.path.exists(xml_entry_path):
            messagebox.showerror("Error", "XML files are missing.")
            return
        else:
            xml_dir = xml_entry_path

    # Check for RGB Core Box Images folder
    rgb_core_box_dir = os.path.join(base_folder, "RGB Core Box Images")
    if not os.path.exists(rgb_core_box_dir) or not os.listdir(rgb_core_box_dir):
        messagebox.showerror("Error", "RGB Core Box Images folder is missing or empty.")
        return

    # First try Masked_Coreg_HSI
    swir_dir = os.path.join(base_folder, "Masked_Coreg_HSI")
    if not os.path.exists(swir_dir) or not os.listdir(swir_dir):
        # If SWIR_HSI_Files is missing/empty, try Corrected_SWIR
        corrected_swir = os.path.join(base_folder, "Corrected_SWIR")
        if not os.path.exists(corrected_swir) or not os.listdir(corrected_swir):
            messagebox.showerror("Error", "Masked_Coreg_HSI and Corrected_SWIR are both missing or empty.")
            return
        else:
            swir_dir = corrected_swir

    # Create output folder if not existing
    output_dir = os.path.join(base_folder, "RGB Core Pieces")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    txt_file_path = os.path.join(base_folder, "core_images_list.txt")

    old_stdout = sys.stdout
    sys.stdout = TextRedirector(log_widget, "stdout")
    try:
        with open(txt_file_path, "a") as txt_file:
            for rgb_filename in os.listdir(rgb_core_box_dir):
                if not rgb_filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    continue
                if "_ext" in rgb_filename:
                    print(f"Skipping already processed file: {rgb_filename}")
                    sys.stdout.flush()
                    continue

                rgb_image_path = os.path.join(rgb_core_box_dir, rgb_filename)
                print(f"\nProcessing RGB image: {rgb_filename}")
                sys.stdout.flush()

                # Attempt to find a UUID in { ... } brackets
                uuid_match = re.search(r"\{.*?\}", rgb_filename)
                if not uuid_match:
                    print(f"  [WARN] No valid UUID found in {rgb_filename}. Skipping.")
                    sys.stdout.flush()
                    continue
                uuid = uuid_match.group(0)

                # Try matching an XML
                matching_xml_files = [
                    f for f in os.listdir(xml_dir)
                    if uuid in f and f.lower().endswith('.xml')
                ]
                if not matching_xml_files:
                    print(f"  [WARN] No XML file found for UUID {uuid}. Skipping.")
                    sys.stdout.flush()
                    continue

                xml_file_path = os.path.join(xml_dir, matching_xml_files[0])
                print(f"  Found XML: {os.path.basename(xml_file_path)}")
                sys.stdout.flush()
                try:
                    tree = ET.parse(xml_file_path)
                except Exception as e:
                    print(f"  [ERROR] Could not parse {xml_file_path}: {e}")
                    sys.stdout.flush()
                    continue

                root_xml = tree.getroot()
                image2d_el = root_xml.find('.//image2D')
                if image2d_el is not None:
                    dims_el = image2d_el.find('dimensions')
                    if dims_el is not None:
                        image2d_width_m = float(dims_el.get('x','1.0'))
                        image2d_height_m= float(dims_el.get('y','1.0'))
                    else:
                        image2d_width_m, image2d_height_m=1.0,1.0

                    transform_el = image2d_el.find('transform')
                    if transform_el is not None:
                        translate_el= transform_el.find('translate')
                        if translate_el is not None:
                            image2d_trans_x= float(translate_el.get('x','0.0'))
                            image2d_trans_y= float(translate_el.get('y','0.0'))
                        else:
                            image2d_trans_x,image2d_trans_y=0.0,0.0
                    else:
                        image2d_trans_x,image2d_trans_y=0.0,0.0
                else:
                    image2d_width_m,image2d_height_m=1.0,1.0
                    image2d_trans_x,image2d_trans_y=0.0,0.0

                core_box_def = root_xml.find('.//CoreBoxDef')
                if core_box_def is None:
                    print(f"  [ERROR] No <CoreBoxDef> in {xml_file_path}. Skipping.")
                    sys.stdout.flush()
                    continue

                corebox_trans_x= float(core_box_def.get('Translation-X','0.0'))
                corebox_trans_y= float(core_box_def.get('Translation-Y','0.0'))
                box_rot_deg=    float(core_box_def.get('Rotation','0'))
                box_scaling_x=  float(core_box_def.get('ScalingX','1'))
                box_scaling_y=  float(core_box_def.get('ScalingY','1'))

                box_def_el= core_box_def.find('BoxDefinition')
                if box_def_el is None:
                    print(f"  [ERROR] No <BoxDefinition> in {xml_file_path}. Skipping.")
                    sys.stdout.flush()
                    continue

                ext_dims_el= box_def_el.find('ExternalDims')
                if ext_dims_el is None:
                    print(f"  [ERROR] No <ExternalDims> in {xml_file_path}. Skipping.")
                    sys.stdout.flush()
                    continue

                ext_width_m=  float(ext_dims_el.get('Width','1.0'))
                ext_height_m= float(ext_dims_el.get('Height','1.0'))
                external_width=  float(box_def_el.get('ExternalWidth','0.0'))
                external_height= float(box_def_el.get('ExternalHeight','0.0'))
                internal_width=  float(box_def_el.get('InternalWidth','0.0'))
                num_compartments= int(box_def_el.get('NumCompartments','1'))

                final_box_width_m  = ext_width_m  * box_scaling_x
                final_box_height_m = ext_height_m * box_scaling_y

                core_pieces_el= core_box_def.find('.//CorePieces')
                if core_pieces_el is None:
                    print(f"  [ERROR] No <CorePieces> in {xml_file_path}. Skipping.")
                    sys.stdout.flush()
                    continue

                piece_list= core_pieces_el.findall('CorePiece')
                if not piece_list:
                    print(f"  [ERROR] No <CorePiece> entries in {xml_file_path}. Skipping.")
                    sys.stdout.flush()
                    continue

                final_trans_x= corebox_trans_x - image2d_trans_x
                final_trans_y= corebox_trans_y - image2d_trans_y

                # Load original image
                image_cv_original = cv2.imread(rgb_image_path)
                if image_cv_original is None:
                    print(f"  [ERROR] Could not load image: {rgb_image_path}")
                    sys.stdout.flush()
                    continue

                # Get original file size for quality estimation
                original_size = os.path.getsize(rgb_image_path)
                
                # Apply enhancement to a copy of the image
                print(f"  Applying enhancement...")
                sys.stdout.flush()
                image_cv_enhanced = enhance_core_box_image_fast(image_cv_original.copy())
                
                # Create a temporary enhanced version with reduced quality
                estimated_quality = estimate_jpeg_quality_for_size(original_size)
                _, temp_buffer = cv2.imencode('.jpg', image_cv_enhanced, [cv2.IMWRITE_JPEG_QUALITY, estimated_quality])
                image_cv = cv2.imdecode(temp_buffer, cv2.IMREAD_COLOR)
                
                print(f"  Enhanced with quality setting: {estimated_quality}")
                sys.stdout.flush()

                img_h, img_w= image_cv.shape[:2]
                with Image.open(rgb_image_path) as pil_img:
                    xdpi, ydpi= pil_img.info.get('dpi',(96,96))

                scale_x= img_w/ image2d_width_m
                scale_y= img_h/ image2d_height_m
                print(f"  Image dimensions: {img_w}x{img_h} px; Scale: ({scale_x:.3f}, {scale_y:.3f}) px/m")
                sys.stdout.flush()

                def rotate_point(x_m, y_m, pivot_x_m, pivot_y_m, deg):
                    if abs(deg)<1e-9:
                        return x_m, y_m
                    rad= math.radians(deg)
                    dx= x_m- pivot_x_m
                    dy= y_m- pivot_y_m
                    rx= dx*math.cos(rad)- dy*math.sin(rad)
                    ry= dx*math.sin(rad)+ dy*math.cos(rad)
                    return pivot_x_m+rx, pivot_y_m+ry

                def box_local_to_pixels(x_m, y_m):
                    world_x= final_trans_x+ x_m
                    world_y= final_trans_y+ y_m
                    rx_m, ry_m= rotate_point(world_x, world_y, final_trans_x, final_trans_y, box_rot_deg)
                    px= rx_m* scale_x
                    py= ry_m* scale_y
                    return px, py

                def row_top_bottom(i):
                    usable_vertical= final_box_height_m - 2*external_height - (num_compartments-1)*internal_width
                    top_m= external_height+ i*(usable_vertical/num_compartments+ internal_width)
                    bot_m= top_m+ (usable_vertical/num_compartments)
                    return top_m,bot_m

                usable_horizontal= final_box_width_m - 2* external_width
                if usable_horizontal<0:
                    print(f"  [ERROR] Not enough horizontal space in box definition for {xml_file_path}. Skipping.")
                    sys.stdout.flush()
                    continue

                cropped_pieces= []
                for idx,piece_el in enumerate(piece_list):
                    try:
                        length_rel= float(piece_el.get('LengthRel','1.0'))
                        offset_rel= float(piece_el.get('OffsetRel','0.0'))
                        row_idx= int(piece_el.get('Row','0'))
                    except Exception as e:
                        print(f"  [WARN] Error reading CorePiece {idx}: {e}")
                        sys.stdout.flush()
                        continue

                    top_m, bot_m= row_top_bottom(row_idx)
                    piece_left_m= external_width+ offset_rel* usable_horizontal
                    piece_width_m= length_rel* usable_horizontal
                    piece_right_m= piece_left_m+ piece_width_m

                    tl_px,tl_py= box_local_to_pixels(piece_left_m, top_m)
                    br_px,br_py= box_local_to_pixels(piece_right_m, bot_m)

                    x0,y0= int(round(tl_px)), int(round(tl_py))
                    x1,y1= int(round(br_px)), int(round(br_py))

                    x_min, x_max= min(x0,x1), max(x0,x1)
                    y_min, y_max= min(y0,y1), max(y0,y1)
                    w_px= x_max- x_min
                    h_px= y_max- y_min

                    if x_min<0 or y_min<0 or x_max>img_w or y_max>img_h:
                        print(f"  [WARN] Piece {idx} out of image bounds. Skipping.")
                        sys.stdout.flush()
                        continue
                    if w_px<2 or h_px<2:
                        print(f"  [WARN] Piece {idx} too small: {w_px}x{h_px} px. Skipping.")
                        sys.stdout.flush()
                        continue

                    # Extract from the enhanced image
                    crop_img= image_cv[y_min:y_max, x_min:x_max]
                    cropped_pieces.append((idx,crop_img))
                    print(f"  Extracted piece {idx}: bounds=({x_min},{y_min}) to ({x_max},{y_max}).")
                    sys.stdout.flush()

                if not cropped_pieces:
                    print(f"  [WARN] No valid pieces extracted from {rgb_filename}.")
                    sys.stdout.flush()
                    continue

                # find matching SWIR folder => rename pieces
                hsi_folder=None
                for folder in os.listdir(swir_dir):
                    if uuid in folder:
                        hsi_folder= os.path.join(swir_dir, folder)
                        break
                if hsi_folder is None:
                    print(f"  [WARN] No matching HSI folder for UUID {uuid}. Skipping renaming.")
                    sys.stdout.flush()
                    continue

                hsi_files= [f for f in os.listdir(hsi_folder) if f.lower().endswith('.hdr')]
                if not hsi_files:
                    print(f"  [WARN] No .hdr files found in HSI folder {hsi_folder}.")
                    sys.stdout.flush()
                    continue

                try:
                    hsi_files_sorted= sorted(hsi_files, key=lambda x: float(re.match(r"([\d\.]+)", x).group(1)))
                except Exception as e:
                    print(f"  [ERROR] Sorting HSI files failed in {hsi_folder}: {e}")
                    sys.stdout.flush()
                    continue

                if len(hsi_files_sorted)!= len(cropped_pieces):
                    print(f"  [WARN] #HSI files={len(hsi_files_sorted)} != #cropped pieces={len(cropped_pieces)}. Skipping.")
                    sys.stdout.flush()
                    continue

                for (idx,piece_cv),hsi_filename in zip(cropped_pieces,hsi_files_sorted):
                    piece_pil= Image.fromarray(cv2.cvtColor(piece_cv,cv2.COLOR_BGR2RGB))
                    rotated= piece_pil.rotate(-90, expand=True)
                    flipped = rotated.transpose(Image.FLIP_LEFT_RIGHT)
                    
                    new_w,new_h= flipped.size
                    resized= flipped.resize((int(new_w*0.25),int(new_h*0.25)))
                    
                    base_hsi= os.path.splitext(hsi_filename)[0]
                    parts= base_hsi.split('_')
                    
                    
                    if len(parts) >= 2:
                        try:
                            depth_from = float(parts[0])
                            depth_to = float(parts[1])
                        except:
                            print(f"  [ERROR] Depth parse failed for {hsi_filename}")
                            sys.stdout.flush()
                            continue
                    else:
                        print(f"  [WARN] Unexpected HSI filename format: {hsi_filename}. Skipping piece {idx}.")
                        sys.stdout.flush()
                        continue
                    
                    # Use the UUID from the original RGB filename, not from HSI filename
                    formatted_depth_from= f"{depth_from:.3f}"
                    formatted_depth_to  = f"{depth_to:.3f}"
                    new_name= f"{uuid}_{formatted_depth_from}_{formatted_depth_to}.jpg"
                    new_path= os.path.join(output_dir,new_name)
                    resized.save(new_path)
                    txt_file.write(f"{formatted_depth_from}\t{formatted_depth_to}\t{new_path}\n")
                    print(f"  Saved processed piece {idx} => {new_name}")
                    sys.stdout.flush()

                # Rename the ORIGINAL file 
                base, ext= os.path.splitext(rgb_filename)
                new_rgb_filename= base+"_ext"+ ext
                new_rgb_image_path= os.path.join(rgb_core_box_dir,new_rgb_filename)
                os.rename(rgb_image_path,new_rgb_image_path)
                print(f"  Marked RGB file as processed: {new_rgb_filename} (original image preserved)")
                sys.stdout.flush()

        print("\nAll files processed. Core pieces list updated in", txt_file_path)
        messagebox.showinfo("Success", "RGB Core Piece Images extracted and saved successfully.")
        sys.stdout.flush()
        

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred during RGB extraction:\n{e}")
    finally:
        sys.stdout = old_stdout
