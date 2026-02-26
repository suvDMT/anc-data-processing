"""
extraction.py – CODE 1: Extraction Logic
Handles parsing XML, padding HSI data, writing HDR files, and extracting
files from .ancprj archives.
"""
import os, re, sys, glob, zipfile, shutil
import numpy as np
import xml.etree.ElementTree as ET
from datetime import datetime
from tkinter import messagebox

from utils import open_with_buffer, TextRedirector


def parse_dt(val):
    val = val.strip().split(" ")[0]
    try:
        d = datetime.strptime(val, "%Y-%m-%dT%H:%M:%S.%f")
    except:
        d = datetime.strptime(val, "%Y-%m-%dT%H:%M:%S")
    return d.strftime("%Y-%m-%d"), d.strftime("%H:%M:%S")

def hsiDataPadder(raw_path, samples, lines, bands, data_type, interleave):
    if not os.path.isfile(raw_path):
        return
    dt_map = {"12": np.uint16, "4": np.float32, "2": np.int16}
    dt = dt_map.get(data_type, np.uint16)
    with open_with_buffer(raw_path, "rb") as f:
        arr = np.fromfile(f, dt)
    s = int(samples)
    l = int(lines)
    b = int(bands)
    if interleave.lower() == "bil":
        arr = arr.reshape((l, b, s))
        pad = np.zeros((l, b, 384), dt)
        off = (384 - s) // 2
        pad[:, :, off:off+s] = arr
    elif interleave.lower() == "bip":
        arr = arr.reshape((l, s, b))
        pad = np.zeros((l, 384, b), dt)
        off = (384 - s) // 2
        pad[:, off:off+s, :] = arr
    else:  # BSQ
        arr = arr.reshape((b, l, s))
        pad = np.zeros((b, l, 384), dt)
        off = (384 - s) // 2
        pad[:, :, off:off+s] = arr
    with open_with_buffer(raw_path, "wb") as f:
        pad.tofile(f)
    print(f"[PADDED] {raw_path}")
    sys.stdout.flush()  # force immediate flush of the print statement

def writeHdrFile(meta, data, hdr_path):
    metaOrder = [
        "Name","Company","Location","WellID","CoreRun","CoreBox","Date",
        "Depth From","Depth To","Length","Diameter","Slabbed","Geologist",
        "RecordedBy","Comment","DepthInEarth","DepthInRock","TotalDepth From",
        "BottomElevation","RockElevation","CoreRecovery","scan length[mm]",
        "Resolution","FramePeriod","IntegrationTime","CameraName","CameraSerial",
        "Measurement-ID","Line-ID"
    ]
    dataOrder = [
        "samples","lines","bands","data type","interleave","file type",
        "misc","byte order","acquisition date","acquisition time","wavelength"
    ]
    sc_len = meta.get("scan length[mm]", "").strip()
    if not sc_len:
        try:
            df = float(meta.get("Depth From","0"))
            dt = float(meta.get("Depth To","0"))
            meta["scan length[mm]"] = f"{(dt - df)*1000:.4f}"
        except:
            meta["scan length[mm]"] = "0.0"

    try:
        ln_val = int(data.get("lines","0"))
        s_len  = float(meta.get("scan length[mm]", "0"))
        if ln_val>0 and s_len>0:
            meta["Resolution"] = f"{ln_val/s_len:.4f} pixel/mm"
        else:
            meta["Resolution"] = "UNKNOWN"
    except:
        meta["Resolution"] = "UNKNOWN"

    data["data type"] = "12"  # force data type=12
    with open_with_buffer(hdr_path, "w") as fw:
        fw.write("ENVI\ndescription = {\n")
        for k in metaOrder:
            fw.write(f"{k} = {meta.get(k,'0.0')}\n")
        fw.write("}\n")
        for k in dataOrder:
            fw.write(f"{k} = {data.get(k,'BLANK')}\n")

def build_url_dict(root):
    url_map = {}
    blocks = []
    for tname in ["HSIresults","VNIRresults"]:
        b = root.find(f".//{tname}")
        if b is not None:
            blocks.extend(b.findall("HSIresult"))

    for res in blocks:
        line_id = res.findtext("lineId","NoLine")
        camera  = res.findtext("CameraName","")
        cam_ser = res.findtext("CameraSerial","")
        try:
            df = float(res.find(".//startTime/position").text.strip())
            dt = float(res.find(".//stopTime/position").text.strip())
        except:
            df, dt = 0.0, 0.0
        fp = res.findtext("FramePeriod_us","0")
        it = res.findtext("IntegrationTime_us","0")
        st = res.find(".//startTime/time")
        ad, at = ("2025-01-01","00:00:00")
        if st is not None and st.text:
            ad, at = parse_dt(st.text)
        img_node = res.find("Images/*")
        if img_node is None:
            continue
        url_str = img_node.findtext("Url","").lower()
        url_base = os.path.splitext(os.path.basename(url_str))[0]
        smp   = img_node.findtext("Samples","0")
        lns   = img_node.findtext("Lines","0")
        bnd   = img_node.findtext("Bands","0")
        dtyp  = img_node.findtext("DataType","12")
        ilv   = img_node.findtext("Interleave","bil")
        bo    = img_node.findtext("byteorder","0")

        wls = "{ }"
        wtag = img_node.find("Wavelengths")
        if wtag is not None and wtag.text:
            wtxt = wtag.text.replace(";", " ,")
            arr = [x.strip() for x in wtxt.split(",") if x.strip()]
            wls = "{ " + ", ".join(arr) + " }"

        url_map[url_base] = {
            'depth_from':   df,
            'depth_to':     dt,
            'camera':       camera,
            'camera_serial': cam_ser,
            'line_id':      line_id,
            'frameperiod':  fp,
            'integration':  it,
            'acq_date':     ad,
            'acq_time':     at,
            'samples':      smp,
            'lines':        lns,
            'bands':        bnd,
            'dtype':        dtyp,
            'ilv':          ilv,
            'b_order':      bo,
            'wls':          wls
        }
    return url_map

def create_hdrs_and_pad_optimized(xml_path, working_folder, sample_info):
    if not os.path.isfile(xml_path):
        return
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except:
        return

    url_dict = build_url_dict(root)
    for f in os.listdir(working_folder):
        if not f.lower().endswith(".raw"):
            continue
        raw_noext_lower = os.path.splitext(f)[0].lower()
        if raw_noext_lower not in url_dict:
            print(f"[WARN] No matching block for {f}")
            sys.stdout.flush()
            continue

        info = url_dict[raw_noext_lower]
        df, dt   = info['depth_from'], info['depth_to']
        camera   = info['camera']
        cam_ser  = info['camera_serial']
        line_id  = info['line_id']
        fp       = info['frameperiod']
        it       = info['integration']
        ad, at   = info['acq_date'], info['acq_time']
        smp      = info['samples']
        lns      = info['lines']
        bnd      = info['bands']
        dtyp     = info['dtype']
        ilv      = info['ilv']
        bo       = info['b_order']
        wls      = info['wls']

        raw_path = os.path.join(working_folder, f)
        hdr_path = os.path.join(working_folder, raw_noext_lower + ".hdr")

        meta = dict(sample_info)
        meta["Depth From"]       = f"{df:.6f}"
        meta["Depth To"]         = f"{dt:.6f}"
        meta["FramePeriod"]      = fp
        meta["IntegrationTime"]  = it
        meta["CameraName"]       = camera
        meta["CameraSerial"]     = cam_ser
        meta["Line-ID"]          = line_id

        data = {
            "samples": smp,
            "lines": lns,
            "bands": bnd,
            "data type": dtyp,
            "interleave": ilv,
            "file type": "ENVI",
            "misc": "empty",
            "byte order": bo,
            "acquisition date": ad,
            "acquisition time": at,
            "wavelength": wls
        }
        writeHdrFile(meta, data, hdr_path)

        # Pad if needed
        try:
            si_i = int(smp)
            if si_i < 384:
                hsiDataPadder(raw_path, smp, lns, bnd, dtyp, ilv)
        except:
            pass

        new_hdr_name = f"{df:.3f}_{dt:.3f}_{line_id}.hdr"
        new_raw_name = f"{df:.3f}_{dt:.3f}_{line_id}.raw"
        os.rename(hdr_path, os.path.join(working_folder, new_hdr_name))
        os.rename(raw_path, os.path.join(working_folder, new_raw_name))
        print(f"[PROCESSED] {f} => {new_hdr_name} / {new_raw_name}")
        sys.stdout.flush()

def extract_and_rename(base_folder):
    xml_dir  = os.path.join(base_folder,"XML")
    wr_dir   = os.path.join(base_folder,"Extracted_WR")
    rgb_dir  = os.path.join(base_folder,"RGB Core Box Images")
    swir_dir = os.path.join(base_folder,"SWIR_HSI_Files")
    vnir_dir = os.path.join(base_folder,"VNIR_HSI_Files")

    for d in [xml_dir, wr_dir, rgb_dir, swir_dir, vnir_dir]:
        os.makedirs(d, exist_ok=True)

    for file in os.listdir(base_folder):
        if not file.lower().endswith(".ancprj"):
            continue
        if "_processed" in file.lower():
            print(f"[SKIP] {file} => already processed.")
            sys.stdout.flush()
            continue

        ancprj_path = os.path.join(base_folder, file)
        base_noext  = os.path.splitext(file)[0]
        zip_name    = base_noext + ".zip"
        zip_path    = os.path.join(base_folder, zip_name)

        os.rename(ancprj_path, zip_path)
        print(f"Renamed {file} => {zip_name}")
        sys.stdout.flush()

        temp_folder = os.path.join(base_folder, base_noext + "_temp")
        os.makedirs(temp_folder, exist_ok=True)

        xml_extracted    = None
        meas_id_for_rgb  = "NoID"

        with zipfile.ZipFile(zip_path, "r") as zf:
            # 1) find the .xml to parse measurement ID
            for info in zf.infolist():
                lname = info.filename.lower()
                if "results" in lname and not ("swirimages" in lname or "vnirimages" in lname):
                    continue
                if lname.endswith(".xml"):
                    xdest = os.path.join(temp_folder, os.path.basename(info.filename))
                    # Speed up extraction with bigger buffering:
                    with zf.open(info) as src, open_with_buffer(xdest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    xml_extracted = xdest
                    try:
                        dxml = ET.parse(xdest)
                        rxml = dxml.getroot()
                        meas_id_for_rgb = rxml.findtext(".//measurement/id", "NoID")
                    except:
                        pass

            # 2) extract raw / WR / RGB
            for info in zf.infolist():
                lname = info.filename.lower()
                if "results" in lname and not ("swirimages" in lname or "vnirimages" in lname):
                    continue
                if lname.endswith(".xml"):
                    continue
                if ("neoreftarget_scan.envi" in lname or "neoreftarget_scan.hdr" in lname):
                    suffix = ""
                    if "swirimages" in lname:
                        suffix = "_SWIR"
                    elif "vnirimages" in lname:
                        suffix = "_VNIR"
                    
                    wr_out = f"{base_noext}_NeoRefTarget_Scan{suffix}" + os.path.splitext(info.filename)[1]
                    with zf.open(info) as src, open_with_buffer(os.path.join(wr_dir, wr_out), "wb") as dst:
                        shutil.copyfileobj(src, dst)
                
                elif "referencepaneldefinition" in lname.lower() and ("swirimages" in lname or "vnirimages" in lname):
                    suffix = ""
                    if "swirimages" in lname:
                        suffix = "_SWIR"
                    elif "vnirimages" in lname:
                        suffix = "_VNIR"
                    
                    # Explicitly extract only to the Extracted_WR folder with a specific name
                    wr_out = f"{base_noext}_ReferencePanelDefinition{suffix}" + os.path.splitext(info.filename)[1]
                    wr_dest = os.path.join(wr_dir, wr_out)
                    
                    with zf.open(info) as src, open_with_buffer(wr_dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    
                    print(f"[EXTRACTED REFERENCE PANEL] => {wr_out} to {wr_dir}")
                    sys.stdout.flush()

                elif lname.endswith(".raw") and ("swirimages" in lname or "vnirimages" in lname) and "referencepaneldefinition" not in lname.lower():
                    out_raw = os.path.join(temp_folder, os.path.basename(info.filename))
                    with zf.open(info) as src, open_with_buffer(out_raw, "wb") as dst:
                        shutil.copyfileobj(src, dst)

                elif info.filename.endswith("RGBScanner.jpg"):
                    out_jpg = f"{base_noext}_{meas_id_for_rgb}.jpg"
                    with zf.open(info) as src, open_with_buffer(os.path.join(rgb_dir, out_jpg), "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    print(f"[EXTRACTED RGB] => {out_jpg}")
                    sys.stdout.flush()

        final_xml_path = None
        sample_info = {}
        depth_val = "NoDepth"
        real_mid = "NoID"

        if xml_extracted and os.path.exists(xml_extracted):
            try:
                doc = ET.parse(xml_extracted)
                rt  = doc.getroot()
                real_mid = rt.findtext(".//measurement/id", "project")
                sample_node = rt.find(".//measurement/sample")
                if sample_node is not None:
                    sample_info = {
                        "Name":         sample_node.findtext("Name","BLANK"),
                        "Company":      sample_node.findtext("Company","BLANK"),
                        "Location":     sample_node.findtext("Location","BLANK"),
                        "WellID":       sample_node.findtext("WellID","BLANK"),
                        "CoreRun":      sample_node.findtext("CoreRun","0"),
                        "CoreBox":      sample_node.findtext("CoreBox","0"),
                        "Date":         sample_node.findtext("Date","BLANK"),
                        "Length":       sample_node.findtext("Length","0"),
                        "Diameter":     sample_node.findtext("Diameter","0"),
                        "Slabbed":      sample_node.findtext("Slabbed","(null)"),
                        "Geologist":    sample_node.findtext("Geologist","BLANK"),
                        "RecordedBy":   sample_node.findtext("RecordedBy","BLANK"),
                        "Comment":      sample_node.findtext("Comment",""),
                        "DepthInEarth": sample_node.findtext("DepthInEarth","0"),
                        "DepthInRock":  sample_node.findtext("DepthInRock","0"),
                        "TotalDepth From": sample_node.findtext("TotalDepth","0"),
                        "BottomElevation": sample_node.findtext("BottomElevation","0"),
                        "RockElevation":   sample_node.findtext("RockElevation","0"),
                        "CoreRecovery":    sample_node.findtext("CoreRecovery","100"),
                        "Measurement-ID":  real_mid
                    }
                depth_val = rt.findtext(".//Depth","NoDepth")
            except:
                sample_info= {}
            new_xml_name = f"{real_mid}.xml"
            final_xml_path = os.path.join(xml_dir, new_xml_name)
            shutil.move(xml_extracted, final_xml_path)

        # subfolder => {Depth}_{ancprjBase}_{measurementID}
        subfolder_name = f"{depth_val}_{base_noext}_{real_mid}"

        if final_xml_path and os.path.isfile(final_xml_path):
            create_hdrs_and_pad_optimized(final_xml_path, temp_folder, sample_info)

        swir_sub = os.path.join(swir_dir, subfolder_name)
        vnir_sub = os.path.join(vnir_dir, subfolder_name)
        os.makedirs(swir_sub, exist_ok=True)
        os.makedirs(vnir_sub, exist_ok=True)

        for fx in os.listdir(temp_folder):
            if not fx.lower().endswith(".hdr"):
                continue
            hdr_path = os.path.join(temp_folder, fx)
            raw_path = os.path.splitext(hdr_path)[0] + ".raw"
            if not os.path.isfile(raw_path):
                continue

            # parse camera
            cam = None
            with open_with_buffer(hdr_path, "r") as rr:
                lines = rr.readlines()
            for ll in lines:
                if ll.strip().startswith("CameraName"):
                    parts= ll.split("=",1)
                    if len(parts)==2:
                        cam= parts[1].strip()
                    break

            if cam and ("vnir" in cam.lower()):
                dst_hdr = os.path.join(vnir_sub, fx)
                dst_raw = os.path.join(vnir_sub, os.path.basename(raw_path))
                shutil.move(hdr_path, dst_hdr)
                shutil.move(raw_path, dst_raw)
                print(f"[SORTED: VNIR] => {fx} => {vnir_sub}")
                sys.stdout.flush()
            else:
                dst_hdr = os.path.join(swir_sub, fx)
                dst_raw = os.path.join(swir_sub, os.path.basename(raw_path))
                shutil.move(hdr_path, dst_hdr)
                shutil.move(raw_path, dst_raw)
                print(f"[SORTED: SWIR] => {fx} => {swir_sub}")
                sys.stdout.flush()

        shutil.rmtree(temp_folder)
        os.rename(zip_path, os.path.join(base_folder, f"{base_noext}_processed.ancprj"))
        print(f"[DONE] {zip_name} => {base_noext}_processed.ancprj")
        sys.stdout.flush()

    print("Extraction complete.\n")
# ─────────────────────────────────────────────────────────────────────────────


def rename_and_extract(folder_path, log_widget):
    """GUI callback — reads widget values, then delegates to extract_and_rename."""
    base_folder = folder_path.strip()
    if not base_folder or not os.path.isdir(base_folder):
        messagebox.showerror("Error", "Please provide a valid ANCPRJ folder path.")
        return
    old_stdout = sys.stdout
    sys.stdout = TextRedirector(log_widget, "stdout")
    try:
        extract_and_rename(base_folder)
        messagebox.showinfo("Success", "Extraction complete.")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred during extraction:\n{e}")
    finally:
        sys.stdout = old_stdout
