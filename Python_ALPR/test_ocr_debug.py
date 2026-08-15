"""
Script test OCR don gian - chup 1 anh tu camera va chay EasyOCR
Chay: python test_ocr_debug.py
"""
import cv2
import numpy as np
import urllib.request
import easyocr
import sys
import json
import os

def p(msg):
    sys.stdout.write(str(msg) + "\n")
    sys.stdout.flush()

# Doc IP camera tu config.json
ip_url = "http://192.168.42.129:8080/photo.jpg"
if os.path.exists("config.json"):
    try:
        with open("config.json") as f:
            cfg = json.load(f)
            ip_url = cfg.get("ip_camera_url", ip_url)
    except:
        pass

# Doi sang endpoint /photo.jpg neu chua co
if "/photo.jpg" not in ip_url:
    ip_url = ip_url.rstrip("/") + "/photo.jpg"

p("=" * 60)
p(f"  TEST OCR DEBUG TOOL")
p(f"  Camera: {ip_url}")
p("=" * 60)

# =========================================================
# BUOC 1: Lay anh tu camera
# =========================================================
p("\n[1] Dang lay anh tu IP Webcam...")
frame = None
try:
    req = urllib.request.urlopen(ip_url, timeout=5)
    arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
    frame = cv2.imdecode(arr, -1)
    if frame is not None:
        p(f"[1] OK! Kich thuoc anh: {frame.shape[1]}x{frame.shape[0]} px")
        cv2.imwrite("debug_original.jpg", frame)
        p("[1] Da luu anh goc -> debug_original.jpg")
    else:
        p("[1] LOI: cv2.imdecode tra ve None! Anh bi hong.")
        sys.exit(1)
except Exception as e:
    p(f"[1] LOI: Khong lay duoc anh tu camera: {e}")
    p(f"    Kiem tra lai:")
    p(f"    - IP Webcam App co dang bat khong?")
    p(f"    - Dien thoai va may tinh co cung mang WiFi?")
    p(f"    - Thu mo trinh duyet va vao: {ip_url}")
    sys.exit(1)

# =========================================================
# BUOC 2: Tao cac phien ban xu ly
# =========================================================
p("\n[2] Tao cac phien ban anh xu ly...")
variants = {}

gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
p(f"[2] Anh xam: {gray.shape}")

# Phong to 2x
big = cv2.resize(gray, (gray.shape[1]*2, gray.shape[0]*2), interpolation=cv2.INTER_CUBIC)
p(f"[2] Anh phong to 2x: {big.shape}")

# CLAHE
clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
clahe_img = clahe.apply(big)

# Nguong hoa Otsu
_, otsu = cv2.threshold(clahe_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
_, otsu_inv = cv2.threshold(clahe_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

variants = {
    "anh_goc": frame,
    "xam_2x": big,
    "clahe_2x": clahe_img,
    "otsu_2x": otsu,
    "otsu_inv_2x": otsu_inv,
}

for name, img in variants.items():
    path = f"debug_{name}.jpg"
    cv2.imwrite(path, img)
    p(f"[2] Da luu -> {path}")

# =========================================================
# BUOC 3: Khoi tao EasyOCR
# =========================================================
p("\n[3] Khoi tao EasyOCR (co the mat 30-60 giay)...")
import warnings
warnings.filterwarnings("ignore")
reader = easyocr.Reader(['en'], gpu=False, verbose=False)
p("[3] EasyOCR san sang!")

# =========================================================
# BUOC 4: Chay OCR tren tung phien ban
# =========================================================
p("\n[4] Chay EasyOCR tren tung phien ban anh...")
p("-" * 60)

all_found = []

for name, img in variants.items():
    p(f"\n  >> Phien ban: [{name}]")
    try:
        # Chay EasyOCR KHONG co bat ky tham so phuc tap nao
        results = reader.readtext(img, detail=1)
        
        if not results:
            p(f"     -> Khong tim thay chu gi")
        else:
            p(f"     -> Tim thay {len(results)} vung chu:")
            for (bbox_pts, text, conf) in results:
                p(f"        text='{text}'  conf={conf:.3f}")
                if conf > 0.2 and len(text.strip()) >= 2:
                    all_found.append((text, conf, name))
    except Exception as e:
        p(f"     -> LOI khi chay EasyOCR: {e}")

# =========================================================
# BUOC 5: Ket qua
# =========================================================
p("\n" + "=" * 60)
p("  KET QUA TONG HOP")
p("=" * 60)

if all_found:
    p(f"Tim thay {len(all_found)} vung chu co the doc duoc:")
    for text, conf, source in sorted(all_found, key=lambda x: -x[1]):
        p(f"  '{text}'  (conf={conf:.3f}, tu={source})")
else:
    p("KHONG DOC DUOC KY TU NAO TU BAT KY PHIEN BAN ANH NAO!")
    p("\nNguyen nhan co the:")
    p("  1. Anh qua toi/sang - Chinh do sang IP Webcam")
    p("  2. Anh bi mo/rung - Camera chua on dinh, thu chup lai")
    p("  3. Khong co bien so trong anh - Dua bien so vao truoc khi chay")
    p("  4. Do phan giai qua thap - Cho camera zoom vao bien so")

p("\nHay gui cac file debug_*.jpg cho ky su de phan tich!")
p("=" * 60)
