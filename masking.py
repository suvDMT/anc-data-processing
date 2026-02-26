"""
masking.py - CODE 4: Mask HSI Files
Applies a pre-trained PyTorch model via subprocess (temp script).
All heavy model/PIL/plt code runs inside the subprocess script string,
exactly as in the original notebook. The GUI callback mask_hsi_files()
accepts folder_path, mask_path and log_widget instead of reading from
global Tkinter widget variables.
"""
import os
import sys
import subprocess
import tempfile

from tkinter import messagebox

from config import MASK_MODEL_PATH
from utils import TextRedirector


# ── Pure helper functions (also embedded verbatim inside the subprocess script)

def clean_directory_name(name):
    """Clean name by replacing first UUID with VNIR, keep second UUID."""
    import re
    uuid_pattern = r'\\{[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}\\}'
    cleaned = re.sub(uuid_pattern, '{VNIR}', name, count=1)
    return cleaned


def read_hdr(hdr_file):
    hdr = {}
    with open(hdr_file, 'r') as f:
        for line in f:
            if '=' in line:
                key, value = line.split('=', 1)
                hdr[key.strip().lower()] = value.strip()
    return hdr


def normalize_band(band):
    import numpy as np
    norm = np.clip(band, 0, 1)
    return (norm * 255).astype(np.uint8)


def pad_to_divisible_by_32(image):
    """Pad image to make dimensions divisible by 32."""
    import cv2
    height, width = image.shape[:2]
    pad_height = (32 - height % 32) % 32
    pad_width  = (32 - width  % 32) % 32
    if pad_height > 0 or pad_width > 0:
        padded_image = cv2.copyMakeBorder(
            image,
            top=0, bottom=pad_height,
            left=0, right=pad_width,
            borderType=cv2.BORDER_REFLECT
        )
        return padded_image, (height, width), (pad_height, pad_width)
    return image, (height, width), (0, 0)


def preprocess_image(image, preprocessing_fn):
    """Preprocess image for inference with padding."""
    import torch
    original_shape = image.shape[:2]
    image, original_dims, padding = pad_to_divisible_by_32(image)
    image = preprocessing_fn(image)
    image_tensor = torch.from_numpy(image.transpose(2, 0, 1)).float().unsqueeze(0)
    return image_tensor, original_dims, padding


_SUBPROCESS_SCRIPT = 'import os\nimport sys\nimport re\nimport numpy as np\nimport matplotlib.pyplot as plt\nfrom pathlib import Path\nimport torch\nimport cv2\nimport segmentation_models_pytorch as smp\nfrom PIL import Image\n\nENCODER         = \'efficientnet-b4\'\nENCODER_WEIGHTS = \'imagenet\'\n\n\ndef clean_directory_name(name):\n    uuid_pattern = r\'{[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}}\'\n    cleaned = re.sub(uuid_pattern, \'{VNIR}\', name, count=1)\n    return cleaned\n\n\ndef read_hdr(hdr_file):\n    hdr = {}\n    with open(hdr_file, \'r\') as f:\n        for line in f:\n            if \'=\' in line:\n                key, value = line.split(\'=\', 1)\n                hdr[key.strip().lower()] = value.strip()\n    return hdr\n\n\ndef normalize_band(band):\n    norm = np.clip(band, 0, 1)\n    return (norm * 255).astype(np.uint8)\n\n\ndef pad_to_divisible_by_32(image):\n    height, width = image.shape[:2]\n    pad_height = (32 - height % 32) % 32\n    pad_width  = (32 - width  % 32) % 32\n    if pad_height > 0 or pad_width > 0:\n        padded_image = cv2.copyMakeBorder(\n            image,\n            top=0, bottom=pad_height,\n            left=0, right=pad_width,\n            borderType=cv2.BORDER_REFLECT\n        )\n        return padded_image, (height, width), (pad_height, pad_width)\n    return image, (height, width), (0, 0)\n\n\ndef preprocess_image(image, preprocessing_fn):\n    original_shape = image.shape[:2]\n    image, original_dims, padding = pad_to_divisible_by_32(image)\n    image = preprocessing_fn(image)\n    image_tensor = torch.from_numpy(image.transpose(2, 0, 1)).float().unsqueeze(0)\n    return image_tensor, original_dims, padding\n\n\ndef process_hsi_files(input_dir, output_dir, model_path, px_to_reduce=2):\n    input_dir  = os.path.normpath(input_dir)\n    output_dir = os.path.normpath(output_dir)\n    model_path = os.path.normpath(model_path)\n\n    print(f"Input directory: {input_dir}")\n    print(f"Output directory: {output_dir}")\n    print(f"Model path: {model_path}")\n\n    device = torch.device(\'cuda\' if torch.cuda.is_available() else \'cpu\')\n    print(f"Using device: {device}")\n\n    rgb_output_dir  = os.path.join(output_dir, "false_RGB")\n    mask_output_dir = os.path.join(output_dir, "false_RGB_Masks")\n    os.makedirs(rgb_output_dir,  exist_ok=True)\n    os.makedirs(mask_output_dir, exist_ok=True)\n\n    try:\n        model = torch.load(model_path, map_location=device, weights_only=False)\n        model = model.to(device)\n        model.eval()\n        print(f"Successfully loaded model from {model_path}")\n        preprocessing_fn = smp.encoders.get_preprocessing_fn(ENCODER, ENCODER_WEIGHTS)\n        print(f"Using encoder: {ENCODER} with weights: {ENCODER_WEIGHTS}")\n    except Exception as e:\n        print(f"Error loading model: {e}")\n        return False\n\n    bands_idx = [50, 100, 150]\n\n    img_files = []\n    for root, _, files in os.walk(input_dir):\n        for file in files:\n            if file.lower().endswith(\'.img\') and \'_mskd\' not in file:\n                img_files.append(os.path.join(root, file))\n\n    print(f"Found {len(img_files)} HSI files to process")\n\n    processed_count = 0\n    skipped_count   = 0\n\n    for img_file in img_files:\n        try:\n            file_basename       = os.path.basename(img_file)\n            rel_path            = os.path.relpath(os.path.dirname(img_file), input_dir)\n            rel_path            = os.path.normpath(rel_path)\n            rel_path_clean      = clean_directory_name(rel_path)\n            file_basename_clean = clean_directory_name(file_basename)\n\n            print(f"Processing: {file_basename}")\n            print(f"  Directory: {rel_path} -> {rel_path_clean}")\n            print(f"  Filename:  {file_basename} -> {file_basename_clean}")\n\n            hdr_file = os.path.splitext(img_file)[0] + \'.hdr\'\n            if not os.path.exists(hdr_file):\n                print(f"  Missing HDR file, skipping")\n                continue\n\n            if \'_mskd\' in file_basename:\n                print(f"  Already processed, skipping")\n                skipped_count += 1\n                continue\n\n            output_img_path = os.path.join(output_dir, rel_path_clean, file_basename_clean)\n            if os.path.exists(output_img_path):\n                print(f"  Output already exists, skipping")\n                skipped_count += 1\n                continue\n\n            hdr     = read_hdr(hdr_file)\n            samples = int(hdr.get(\'samples\', 0))\n            lines   = int(hdr.get(\'lines\',   0))\n            bands   = int(hdr.get(\'bands\',   0))\n\n            if samples == 0 or lines == 0 or bands == 0:\n                print(f"  Invalid header information, skipping")\n                continue\n\n            dtype_str = hdr.get(\'data type\', \'4\')\n            if   dtype_str == \'4\' : dtype = np.float32\n            elif dtype_str == \'5\' : dtype = np.float64\n            elif dtype_str == \'12\': dtype = np.uint16\n            else                  : dtype = np.float32\n\n            with open(img_file, \'rb\') as f:\n                raw_data = np.fromfile(f, dtype=dtype)\n\n            if raw_data.size != samples * lines * bands:\n                print(f"  Size mismatch, skipping")\n                continue\n\n            interleave = hdr.get(\'interleave\', \'bil\').lower()\n            if interleave == \'bil\':\n                raw_data = raw_data.reshape((lines, bands, samples))\n                raw_data = raw_data.transpose(0, 2, 1)\n            elif interleave == \'bip\':\n                raw_data = raw_data.reshape((lines, samples, bands))\n            elif interleave == \'bsq\':\n                raw_data = raw_data.reshape((bands, lines, samples))\n                raw_data = raw_data.transpose(1, 2, 0)\n\n            band_indices = [min(idx, bands-1) for idx in bands_idx]\n            r, g, b = [normalize_band(raw_data[:, :, idx]) for idx in band_indices]\n            rgb = np.stack([r, g, b], axis=-1)\n\n            rgb[:, :px_to_reduce,  :] = 0\n            rgb[:, -px_to_reduce:, :] = 0\n\n            output_rgb_subfolder = os.path.join(rgb_output_dir, rel_path_clean)\n            os.makedirs(output_rgb_subfolder, exist_ok=True)\n\n            rgb_output_path = os.path.join(\n                output_rgb_subfolder,\n                f"{os.path.splitext(file_basename_clean)[0]}.png"\n            )\n            plt.imsave(rgb_output_path, rgb)\n            print(f"  Saved RGB image")\n\n            image_tensor, original_dims, padding = preprocess_image(rgb, preprocessing_fn)\n            image_tensor = image_tensor.to(device)\n\n            with torch.no_grad():\n                output      = model(image_tensor)\n                mask        = output.squeeze().cpu().numpy()\n                binary_mask = (mask > 0.5).astype(np.uint8) * 255\n\n                if padding[0] > 0 or padding[1] > 0:\n                    binary_mask = binary_mask[:original_dims[0], :original_dims[1]]\n\n                kernel      = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))\n                binary_mask = cv2.erode(binary_mask, kernel, iterations=1)\n\n                center_col  = binary_mask.shape[1] // 2\n                num_labels, labels = cv2.connectedComponents(binary_mask)\n                for label in range(1, num_labels):\n                    component_mask = (labels == label)\n                    if not np.any(component_mask[:, center_col]):\n                        binary_mask[component_mask] = 0\n\n                contours, _ = cv2.findContours(\n                    binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE\n                )\n                cv2.fillPoly(binary_mask, contours, 255)\n                binary_mask = (binary_mask > 0).astype(np.uint8)\n\n            print(f"  Generated mask with new model")\n\n            mask_output_subfolder = os.path.join(mask_output_dir, rel_path_clean)\n            os.makedirs(mask_output_subfolder, exist_ok=True)\n\n            mask_output_path = os.path.join(\n                mask_output_subfolder,\n                f"{os.path.splitext(file_basename_clean)[0]}.png"\n            )\n            mask_image = Image.fromarray(binary_mask * 255)\n            mask_image.save(mask_output_path)\n            print(f"  Saved mask image")\n\n            mask_resized = np.repeat(binary_mask[:, :, np.newaxis], raw_data.shape[2], axis=2)\n            raw_data[mask_resized == 0] = 0\n            raw_data[:, :px_to_reduce,  :] = 0\n            raw_data[:, -px_to_reduce:, :] = 0\n\n            output_subfolder = os.path.join(output_dir, rel_path_clean)\n            os.makedirs(output_subfolder, exist_ok=True)\n\n            output_img_path = os.path.join(output_subfolder, file_basename_clean)\n            output_hdr_path = os.path.join(\n                output_subfolder,\n                os.path.splitext(file_basename_clean)[0] + \'.hdr\'\n            )\n\n            if interleave == \'bil\':\n                raw_to_save = raw_data.transpose(0, 2, 1)\n            elif interleave == \'bsq\':\n                raw_to_save = raw_data.transpose(2, 0, 1)\n            else:\n                raw_to_save = raw_data\n\n            raw_to_save = np.ascontiguousarray(raw_to_save)\n            with open(output_img_path, \'wb\') as f:\n                raw_to_save.tofile(f)\n\n            with open(hdr_file, \'r\') as src, open(output_hdr_path, \'w\') as dst:\n                for line in src:\n                    dst.write(line)\n\n            print(f"  Saved masked HSI data")\n\n            r_masked, g_masked, b_masked = [\n                normalize_band(raw_data[:, :, idx]) for idx in band_indices\n            ]\n            rgb_masked = np.stack([r_masked, g_masked, b_masked], axis=-1)\n\n            masked_rgb_path = os.path.join(\n                output_rgb_subfolder,\n                f"{os.path.splitext(file_basename_clean)[0]}_masked.png"\n            )\n            plt.imsave(masked_rgb_path, rgb_masked)\n            print(f"  Saved masked RGB preview")\n\n            input_base_no_ext = os.path.splitext(img_file)[0]\n            new_img_path = f"{input_base_no_ext}_mskd.img"\n            new_hdr_path = f"{input_base_no_ext}_mskd.hdr"\n\n            try:\n                os.rename(img_file, new_img_path)\n                os.rename(hdr_file, new_hdr_path)\n                print(f"  Renamed original files with _mskd suffix")\n            except Exception as e:\n                print(f"  Warning: Could not rename original files: {e}")\n\n            processed_count += 1\n            print(f"  Successfully processed")\n\n        except Exception as e:\n            print(f"Error processing {file_basename}: {str(e)}")\n            import traceback\n            traceback.print_exc()\n\n    print(f"\\nMasking process completed:")\n    print(f"  - {processed_count} files processed")\n    print(f"  - {skipped_count} files skipped")\n    return processed_count > 0\n\n\nif __name__ == "__main__":\n    input_dir  = sys.argv[1]\n    output_dir = sys.argv[2]\n    model_path = sys.argv[3]\n    process_hsi_files(input_dir, output_dir, model_path)\n'


# ── GUI callback ──────────────────────────────────────────────────────────────

def mask_hsi_files(folder_path, mask_path, log_widget):
    """
    GUI callback -- accepts folder_path, mask_path and log_widget as parameters
    instead of reading from global Tkinter widget variables.
    Writes a temporary Python script and executes it via subprocess so that
    PyTorch / segmentation_models_pytorch runs in an isolated environment,
    exactly matching the original notebook behaviour.
    """
    import tempfile
    import subprocess

    mask_path   = mask_path.strip()
    base_folder = folder_path.strip()

    # Fall back to Coregistered_HSI inside the main folder if no mask path given
    if not mask_path:
        mask_path = os.path.join(base_folder, "Coregistered_HSI")

    if not os.path.isdir(mask_path):
        messagebox.showerror(
            "Error",
            "Files to be masked directory not found. Please provide a valid path."
        )
        return

    model_path = MASK_MODEL_PATH
    if not os.path.isfile(model_path):
        messagebox.showerror("Error", f"Model file not found at: {model_path}")
        return

    # Output directory logic mirrors the original notebook exactly
    if not mask_path:
        output_dir = os.path.join(base_folder, "Masked_Coreg_HSI")
    else:
        output_dir = os.path.join(os.path.dirname(mask_path), "Masked_HSI")

    os.makedirs(output_dir, exist_ok=True)

    # Write the subprocess script to a temp file
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w') as script_file:
        script_path = script_file.name
        script_file.write(_SUBPROCESS_SCRIPT)

    # Run the subprocess
    old_stdout = sys.stdout
    sys.stdout = TextRedirector(log_widget, "stdout")

    try:
        print("Starting HSI masking process using subprocess...")
        print(f"Input directory: {mask_path}")
        print(f"Output directory: {output_dir}")
        print(f"Model path: {model_path}")
        sys.stdout.flush()

        env = os.environ.copy()
        env["PYTORCH_ALLOW_UNSAFE_SERIALIZATION"] = "1"

        process = subprocess.Popen(
            [sys.executable, script_path, mask_path, output_dir, model_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            env=env
        )

        for line in process.stdout:
            print(line.strip())
            sys.stdout.flush()

        return_code = process.wait()

        if return_code == 0:
            messagebox.showinfo("Success", "HSI masking completed successfully!")
        else:
            messagebox.showerror("Error", f"HSI masking failed with return code {return_code}")

    except Exception as e:
        error_msg = f"An error occurred during masking:\n{str(e)}"
        print(error_msg)
        sys.stdout.flush()
        messagebox.showerror("Error", error_msg)

    finally:
        sys.stdout = old_stdout
        try:
            os.unlink(script_path)
        except Exception:
            pass