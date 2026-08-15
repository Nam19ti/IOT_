import cv2
import re
import threading
from PIL import Image
from core import p

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

VN_PLATE_RE = re.compile(r'^(\d{2,3})([A-Z]{1,2})(\d{4,5})$')

OCR_FIX = {
    'O': '0', 'I': '1', 'L': '1', 'B': '8', 
    'S': '5', 'Z': '2', 'G': '6', 'Q': '0'
}

class HybridOCR:
    def __init__(self, api_key=""):
        self.gemini_model = None
        self._init_gemini(api_key)
        
    def _init_gemini(self, api_key):
        if not GEMINI_AVAILABLE:
            p("[AI] Thu vien google.generativeai chua duoc cai dat.")
            return
        if api_key and api_key.strip():
            try:
                genai.configure(api_key=api_key.strip())
                # Google deprecated 2.5 cho user moi, nen ta dung ban moi nhat 3.5
                self.gemini_model = genai.GenerativeModel('gemini-3.5-flash')
                p("[AI] Gemini API san sang!")
            except Exception as e:
                p(f"[AI ERROR] Gemini: {e}")
                self.gemini_model = None
        else:
            p("[AI] Khong co Gemini API Key. Vui long nhap tren Web UI.")

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

    def _run_gemini(self, img):
        if not self.gemini_model: 
            return "Thieu API Key"
        try:
            pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            prompt = "Read the license plate in this image. Return ONLY the alphanumeric characters without any spaces, dashes, or punctuation. Example: 51G12345"
            res = self.gemini_model.generate_content([prompt, pil_img]).text.strip()
            processed = self._post_process(res)
            return processed if processed else res # Tra ve nguyen ban neu ko regex match de biet sai do dau
        except Exception as e:
            p(f"      -> [GEMINI LOI] {e}")
            return "Loi Ket Noi"

    def process_pipeline(self, frames_data):
        """Xu ly nhieu anh, doc tung anh den khi ra bien so chuan"""
        if not frames_data:
            return "Khong Thay Bien", "None", None

        valid_frames = [f[0] for f in frames_data if f[0] is not None and f[0].size > 0]
        if not valid_frames:
            return "Khong Thay Bien", "None", None

        best_overall = None
        best_frame = valid_frames[0]
        
        if not self.gemini_model:
            return "Thieu API Key", "Gemini", best_frame
            
        # Tinh toan do net cua tung anh va sap xep (Anh net nhat len dau)
        scored_frames = []
        for i, frame in enumerate(valid_frames):
            score = self._get_sharpness(frame)
            scored_frames.append((score, frame, i+1))
            
        scored_frames.sort(key=lambda x: x[0], reverse=True)
        
        p(f"    -> [AI] Đã lọc 3 ảnh. Bắt đầu gửi ảnh nét nhất lên Gemini...")
        
        for score, frame, orig_idx in scored_frames:
            p(f"      -> Đang thử Ảnh gốc số {orig_idx} (Độ nét: {score:.1f})...")
            
            res = self._run_gemini(frame)
            
            if res and res not in ("Khong Thay Bien", "Thieu API Key", "Loi Ket Noi"):
                if self._validate(res):
                    p(f"      -> [OK] Tim thay bien so chuan '{res}'!")
                    return res, "Gemini", frame
                else:
                    p(f"      -> [WARN] Nhan dien ra '{res}' nhung sai dinh dang VN.")
                    # Luu lam backup neu cac anh khac khong tot hon
                    if not best_overall:
                        best_overall = res
                        best_frame = frame
            else:
                p(f"      -> [FAIL] Khong the doc duoc bien so.")
                
        return best_overall if best_overall else "Khong Nhan Dien Duoc", "Gemini", best_frame
