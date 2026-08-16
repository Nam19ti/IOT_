import cv2
import re
import numpy as np
from core import p

# ==========================================
# KHỞI TẠO VÀ KIỂM TRA THƯ VIỆN NHẬN DIỆN
# ==========================================

# Kiểm tra thư viện EasyOCR (Dùng cho nhận diện Offline tại Edge)
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

# Kiểm tra thư viện Google Generative AI (Dùng cho Gemini - Nhận diện Cloud)
try:
    import google.generativeai as genai
    from PIL import Image
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ==========================================
# CẤU HÌNH BIỂN SỐ VÀ TỪ ĐIỂN SỬA LỖI
# ==========================================

# Regex định dạng biển số xe Việt Nam (Hỗ trợ cả ô tô và xe máy)
# Ô tô: 2 số + 1-2 chữ + 4-5 số (VD: 30A12345, 51KT1234)
# Xe máy: 2 số + 1 chữ + 1 số/chữ + 4-5 số (VD: 99E122268)
VN_PLATE_RE = re.compile(r'^(\d{2})([A-Z][A-Z0-9]?)(\d{4,5})$')

# Từ điển tự động sửa các lỗi nhận diện AI thường gặp (Nhầm số thành chữ và ngược lại)
OCR_FIX = {
    'O': '0', 'Q': '0',
    'I': '1', 'J': '1',
    'L': '1', 'B': '8', 
    'S': '5', 'Z': '2', 'G': '6',
    'A': '4', 'T': '7', 'D': '0'
}

class HybridOCR:
    """
    Lớp HybridOCR: Công cụ nhận diện biển số lai (Hybrid)
    Kết hợp giữa sức mạnh của Cloud AI (Gemini) và khả năng dự phòng cực tốt của Edge AI (EasyOCR).
    Mục đích: Đảm bảo độ chính xác cao nhất nhưng vẫn hoạt động được khi rớt mạng.
    """
    def __init__(self, api_key="", mode="gemini"):
        self.reader = None
        self.api_key = api_key
        self.mode = mode
        
        # Tải mô hình EasyOCR tiếng Anh vào bộ nhớ RAM ngay khi khởi động
        # Tắt GPU vì thiết bị nhúng/mini PC thường không có GPU mạnh, chạy CPU vẫn đủ nhanh (~1s)
        if EASYOCR_AVAILABLE:
            p("[AI] Đang nạp mô hình EasyOCR (Offline) vào RAM... Vui lòng đợi.")
            self.reader = easyocr.Reader(['en'], gpu=False)
            p("[AI] EasyOCR Đã sẵn sàng 100% OFFLINE!")
        else:
            p("[AI] Thư viện EasyOCR chưa được cài đặt. Vui lòng chạy: pip install easyocr")
            
        # Nạp cấu hình API Key cho Gemini nếu người dùng chọn chế độ Cloud
        if GEMINI_AVAILABLE and self.api_key:
            genai.configure(api_key=self.api_key)
            p("[AI] Đã nạp cấu hình Google Gemini API!")

    def _fix_ocr(self, text):
        """
        Hàm sửa lỗi ký tự do AI nhận diện sai (Thuật toán Heuristic).
        - Loại bỏ ký tự đặc biệt.
        - Dựa vào vị trí ký tự để ép kiểu (Ví dụ vị trí thứ 3 phải là CHỮ, nếu AI đọc là 8 thì sửa thành B).
        """
        # Xóa mọi ký tự không phải chữ và số, viết hoa toàn bộ
        res = list(re.sub(r'[^A-Z0-9]', '', text.upper()))
        
        # Chỉ xử lý nếu biển số dài từ 7 ký tự trở lên
        if len(res) >= 7:
            # Xác định số lượng chữ số đầu (2 hoặc 3 tùy vào mã tỉnh)
            num_prefix = 2 if not res[2].isdigit() else 3
            
            # Ép phần mã tỉnh phải là số (vd 29, 30)
            for i in range(num_prefix):
                if res[i].isalpha(): res[i] = OCR_FIX.get(res[i], res[i])
            
            # Xác định vùng mã chữ (Vd: A, AB, C1)
            letter_end = num_prefix
            while letter_end < len(res) and letter_end < num_prefix + 2 and res[letter_end].isalpha():
                letter_end += 1
                
            # Ép phần đuôi phải là số (vd: 12345)
            for i in range(letter_end, len(res)):
                if res[i].isalpha():
                    if res[i] in OCR_FIX:
                        res[i] = OCR_FIX[res[i]]
                    elif i == len(res) - 1: # Chữ cái rác ở cuối (ví dụ đọc nhầm ốc vít thành chữ V) thì xóa luôn
                        res[i] = ''
        return ''.join(res)

    def _validate(self, text):
        """Kiểm tra xem chuỗi có khớp đúng định dạng Regex biển số Việt Nam không"""
        if len(text) < 7 or len(text) > 9: return False
        return bool(VN_PLATE_RE.match(text))

    def _post_process(self, raw):
        """
        Quy trình hậu xử lý thông minh (Sliding Window): 
        Lọc biển số khỏi các chữ rác trong nền ảnh (VD: AI đọc là 'HONDA29A12345').
        """
        # Tiền xử lý: Xóa các ký tự không hợp lệ
        raw = re.sub(r'[^A-Z0-9]', '', raw.upper())
        
        # Sửa lỗi đặc thù: Nhiễu viền trái khiến AI đọc dư 1 chữ cái (Ví dụ: 99JE122268, 99HE122268)
        # Nếu xóa chữ cái dư đó mà tạo thành biển hợp lệ thì ưu tiên lấy luôn.
        if len(raw) > 9:
            match = re.match(r'^(\d{2})[A-Z]([A-Z][A-Z0-9]?\d{4,5})$', raw)
            if match:
                candidate = match.group(1) + match.group(2)
                if self._validate(candidate):
                    return candidate

        # 1. Thử tìm ngay một chuỗi khớp hoàn hảo nằm bên trong (Regex Search)
        # Bắt buộc chuỗi cắt ra không được dính liền với số khác (tránh chặt đôi một số dài)
        match = re.search(r'(?<!\d)(\d{2}[A-Z][A-Z0-9]?\d{4,5})(?!\d)', raw)
        if match:
            return match.group(1)
            
        # 2. Nếu không tìm thấy (có thể do lỗi O->0, I->1...), ta trượt cửa sổ cắt từng đoạn
        # dài 7, 8, 9 ký tự và đưa vào hàm _fix_ocr để sửa lỗi.
        for length in [9, 8, 7]: # Ưu tiên biển số dài (9 ký tự) trước
            if len(raw) < length: continue
            for i in range(len(raw) - length + 1):
                substring = raw[i:i+length]
                fixed = self._fix_ocr(substring)
                if self._validate(fixed):
                    return fixed
                    
        # Trả về kết quả thô nếu không có cụm nào sửa thành công (Chấp nhận trả linh tinh để người dùng tự xem)
        return raw

    def _get_sharpness(self, img):
        """Thuật toán đánh giá độ nét của ảnh dùng phương sai Laplacian"""
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return cv2.Laplacian(gray, cv2.CV_64F).var()
        except:
            return 0.0

    def _crop_plate(self, img):
        """
        Khoanh vùng và cắt riêng phần biển số bằng CRAFT Text Detector (EasyOCR).
        Chính xác hơn Haar Cascade và tương thích với OpenCV 5.
        """
        if not self.reader:
            return img
        try:
            # Thu nhỏ tạm thời để detect nhanh vùng chữ
            h, w = img.shape[:2]
            scale = min(800 / float(w), 1.0)
            if scale < 1.0:
                resized = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)
            else:
                resized = img

            horizontal_list, free_list = self.reader.detect(resized)
            if not horizontal_list or len(horizontal_list[0]) == 0:
                return img
                
            bboxes = horizontal_list[0]
            # Lọc các box quá nhỏ (nhiễu)
            max_w = max(b[1] - b[0] for b in bboxes)
            main_boxes = [b for b in bboxes if (b[1] - b[0]) > max_w * 0.3]
            if not main_boxes: main_boxes = bboxes
            
            x_min = min(b[0] for b in main_boxes)
            x_max = max(b[1] for b in main_boxes)
            y_min = min(b[2] for b in main_boxes)
            y_max = max(b[3] for b in main_boxes)
            
            x_min = int(x_min / scale)
            x_max = int(x_max / scale)
            y_min = int(y_min / scale)
            y_max = int(y_max / scale)
            
            pad_x = int((x_max - x_min) * 0.30)
            pad_y = int((y_max - y_min) * 0.30)
            
            x1 = max(0, x_min - pad_x)
            y1 = max(0, y_min - pad_y)
            x2 = min(w, x_max + pad_x)
            y2 = min(h, y_max + pad_y)
            
            cropped = img[y1:y2, x1:x2]
            p("      -> [AI] Đã khoanh vùng cắt biển bằng CRAFT Text Detector thành công!")
            return cropped
        except Exception as e:
            p(f"      -> [CROP LỖI] {e}")
            
        return img # Trả về ảnh gốc nếu lỗi

    def _run_easyocr(self, img):
        """Nhận diện biển số Offline bằng mô hình AI EasyOCR"""
        if not self.reader: 
            return "Thieu Thiet Lap"
        try:
            # Chạy mô hình trích xuất chữ trực tiếp trên ảnh gốc (không nén để giữ nguyên độ nét)
            results = self.reader.readtext(img, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', detail=0)
            if not results:
                return None
            
            # Nối các dòng chữ lại với nhau (để xử lý biển vuông có 2 dòng)
            raw = "".join(results)
            processed = self._post_process(raw)
            return processed if processed else raw
        except Exception as e:
            p(f"      -> [EASYOCR LỖI] {e}")
            return "Loi Phan Mem"

    def _run_gemini(self, img):
        """Nhận diện biển số trên Cloud bằng Google Gemini 3.5 Flash"""
        if not GEMINI_AVAILABLE:
            return "Khong Co Gemini"
        if not self.api_key:
            return "Thieu API Key"
        try:
            # Chuyển đổi định dạng ảnh từ OpenCV (BGR) sang chuẩn PIL (RGB) để đẩy lên Gemini
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel('gemini-3.5-flash')
            
            # Prompt ra lệnh rõ ràng cho Gemini để chỉ lấy đúng chuỗi biển số
            prompt = "Read the license plate number from this image. Output ONLY the alphanumeric string without any spaces or symbols. E.g. '29A12345'. If no plate is found, output 'None'."
            
            response = model.generate_content([prompt, pil_img])
            raw = response.text.strip().upper()
            if raw == "NONE":
                return None
                
            processed = self._post_process(raw)
            return processed if processed else raw
        except Exception as e:
            p(f"      -> [GEMINI LỖI/MẤT MẠNG] {e}")
            return "Mat Mang"

    def process_pipeline(self, frames_data):
        """
        Luồng xử lý (Pipeline) thông minh: Nhận vào nhiều khung hình,
        Lọc ra ảnh nét nhất để ưu tiên chạy AI, nếu thất bại mới chạy các ảnh mờ hơn.
        Hỗ trợ cơ chế Fallback (Tự động chuyển từ Cloud xuống Offline khi rớt mạng).
        """
        if not frames_data:
            return "Khong Thay Bien", "None", None

        # Lọc bỏ các khung hình lỗi/trống
        valid_frames = [f[0] for f in frames_data if f[0] is not None and f[0].size > 0]
        if not valid_frames:
            return "Khong Thay Bien", "None", None

        best_overall = None
        best_frame = valid_frames[0]
        
        if not self.reader:
            return "Chua Cai EasyOCR", "EasyOCR", best_frame
            
        # Lọc và xếp hạng ảnh theo độ nét (Phương sai Laplacian)
        scored_frames = []
        for i, frame in enumerate(valid_frames):
            score = self._get_sharpness(frame)
            scored_frames.append((score, frame, i+1))
            
        # Ưu tiên lấy ảnh sắc nét nhất lên đầu tiên
        scored_frames.sort(key=lambda x: x[0], reverse=True)
        
        # TỐI ƯU TỐC ĐỘ: Chỉ xử lý tối đa 2 ảnh nét nhất thay vì toàn bộ (Tiết kiệm 60% thời gian)
        scored_frames = scored_frames[:2]
        
        p(f"    -> [AI] Bắt đầu chạy Nhận diện trên {len(scored_frames)} ảnh nét nhất... (Chế độ: {self.mode})")
        
        for score, frame, orig_idx in scored_frames:
            p(f"      -> Đang phân tích ảnh gốc số {orig_idx} (Độ nét: {score:.1f})...")
            
            # Cắt vùng biển số
            cropped_frame = self._crop_plate(frame)
            
            res = None
            engine_used = "EasyOCR"
            
            # CHẾ ĐỘ HYBRID: Chạy Gemini trước, nếu rớt mạng thì lập tức Fallback về EasyOCR
            if self.mode == "gemini" and self.api_key:
                p("      -> [AI] Đang gọi Google Gemini API (Cloud)...")
                res = self._run_gemini(cropped_frame)
                
                # Nếu Gemini trả về lỗi mạng hoặc lỗi API, kích hoạt cơ chế Fallback
                if res and res not in ("Mat Mang", "Thieu API Key", "Khong Co Gemini", "Loi Phan Mem", "Khong Thay Bien"):
                    engine_used = "Gemini 1.5"
                else:
                    p("      -> [AI] Gemini thất bại (Mất mạng hoặc Lỗi). TỰ ĐỘNG FALLBACK sang EasyOCR Offline!")
                    res = self._run_easyocr(cropped_frame)
                    engine_used = "EasyOCR (Fallback)"
            else:
                # Chế độ thuần Offline
                res = self._run_easyocr(cropped_frame)
                engine_used = "EasyOCR"
            
            # Đánh giá kết quả
            if res and res not in ("Khong Thay Bien", "Thieu Thiet Lap", "Loi Phan Mem", "Mat Mang", "Thieu API Key"):
                if self._validate(res):
                    p(f"      -> [OK] Tìm thấy biển số chuẩn '{res}' bằng {engine_used}!")
                    return res, engine_used, cropped_frame
                else:
                    p(f"      -> [WARN] Nhận diện ra '{res}' nhưng sai định dạng Biển VN.")
                    # Lưu tạm kết quả sai định dạng vào best_overall để dùng nếu các ảnh khác đều xịt
                    if not best_overall:
                        best_overall = res
                        best_frame = cropped_frame
            else:
                p(f"      -> [FAIL] Không thể đọc được biển số trên ảnh này.")
                
        # Nếu duyệt qua tất cả ảnh mà không có cái nào chuẩn 100%, trả về kết quả khả dĩ nhất
        return best_overall if best_overall else "Khong Nhan Dien Duoc", "EasyOCR", best_frame
