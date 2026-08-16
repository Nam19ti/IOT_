import cv2
import re
import numpy as np
from core import p

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

VN_PLATE_RE = re.compile(r'^(\d{2,3})([A-Z]{1,2})(\d{4,5})$')

OCR_FIX = {
    'O': '0', 'I': '1', 'L': '1', 'B': '8', 
    'S': '5', 'Z': '2', 'G': '6', 'Q': '0',
    'D': '0'
}

class HybridOCR:
    def __init__(self, api_key=""):
        self.reader = None
        if EASYOCR_AVAILABLE:
            p("[AI] Đang nạp mô hình EasyOCR (Offline) vào RAM... Vui lòng đợi.")
            self.reader = easyocr.Reader(['en'], gpu=False) # Dùng GPU nếu có cài CUDA
            p("[AI] EasyOCR đã sẵn sàng 100% OFFLINE!")
        else:
            p("[AI] Thư viện EasyOCR chưa được cài đặt. Vui lòng chạy: pip install easyocr")

    def _fix_ocr(self, text):
        res = list(re.sub(r'[^A-Z0-9]', '', text.upper()))
        if len(res) >= 7:
            num_prefix = 2 if not res[2].isdigit() else 3
            for i in range(num_prefix):
                if res[i].isalpha(): res[i] = OCR_FIX.get(res[i], res[i])
            
            letter_end = num_prefix
            while letter_end < len(res) and letter_end < num_prefix + 2 and res[letter_end].isalpha():
                letter_end += 1
                
            for i in range(letter_end, len(res)):
                if res[i].isalpha() and res[i] in OCR_FIX:
                    res[i] = OCR_FIX[res[i]]
        return ''.join(res)

    def _validate(self, text):
        if len(text) < 7 or len(text) > 9: return False
        return bool(VN_PLATE_RE.match(text))

    def _post_process(self, raw):
        raw = re.sub(r'[^A-Z0-9]', '', raw.upper())
        if self._validate(raw): return raw
        fixed = self._fix_ocr(raw)
        if self._validate(fixed): return fixed
        if len(raw) >= 5: return raw
        return None

    def _get_sharpness(self, img):
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return cv2.Laplacian(gray, cv2.CV_64F).var()
        except:
            return 0.0

    def _run_easyocr(self, img):
        if not self.reader: 
            return "Thieu Thiet Lap"
        try:
            # Chạy nhận diện
            results = self.reader.readtext(img, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', detail=0)
            if not results:
                return None
            
            # Ghép các dòng lại với nhau (Biển số vuông thường có 2 dòng)
            raw = "".join(results)
            processed = self._post_process(raw)
            return processed if processed else raw
        except Exception as e:
            p(f"      -> [EASYOCR LOI] {e}")
            return "Loi Phan Mem"

    def process_pipeline(self, frames_data):
        """Xu ly nhieu anh, doc tung anh den khi ra bien so chuan"""
        if not frames_data:
            return "Khong Thay Bien", "None", None

        valid_frames = [f[0] for f in frames_data if f[0] is not None and f[0].size > 0]
        if not valid_frames:
            return "Khong Thay Bien", "None", None

        best_overall = None
        best_frame = valid_frames[0]
        
        if not self.reader:
            return "Chua Cai EasyOCR", "EasyOCR", best_frame
            
        # Lọc ảnh nét nhất
        scored_frames = []
        for i, frame in enumerate(valid_frames):
            score = self._get_sharpness(frame)
            scored_frames.append((score, frame, i+1))
            
        scored_frames.sort(key=lambda x: x[0], reverse=True)
        
        p(f"    -> [AI] Bắt đầu chạy Nhận diện Offline (EasyOCR) trên ảnh nét nhất...")
        
        for score, frame, orig_idx in scored_frames:
            p(f"      -> Đang phân tích Ảnh gốc số {orig_idx} (Độ nét: {score:.1f})...")
            
            res = self._run_easyocr(frame)
            
            if res and res not in ("Khong Thay Bien", "Thieu Thiet Lap", "Loi Phan Mem"):
                if self._validate(res):
                    p(f"      -> [OK] Tim thay bien so chuan '{res}'!")
                    return res, "EasyOCR", frame
                else:
                    p(f"      -> [WARN] Nhan dien ra '{res}' nhung sai dinh dang VN.")
                    if not best_overall:
                        best_overall = res
                        best_frame = frame
            else:
                p(f"      -> [FAIL] Khong the doc duoc bien so tren anh nay.")
                
        return best_overall if best_overall else "Khong Nhan Dien Duoc", "EasyOCR", best_frame
