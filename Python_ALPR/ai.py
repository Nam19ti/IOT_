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

# Regex chuẩn hóa định dạng biển số Việt Nam (Vd: 29A12345)
# Gồm: 2-3 số đầu (mã tỉnh) + 1-2 chữ cái (mã quận/huyện) + 4-5 số cuối
VN_PLATE_RE = re.compile(r'^(\d{2,3})([A-Z]{1,2})(\d{4,5})$')

# Từ điển tự động sửa các lỗi nhận diện AI thường gặp (Nhầm số thành chữ và ngược lại)
OCR_FIX = {
    'O': '0', 'I': '1', 'L': '1', 'B': '8', 
    'S': '5', 'Z': '2', 'G': '6', 'Q': '0',
    'D': '0'
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
        """Quy trình hậu xử lý chuẩn hóa kết quả thô từ AI"""
        raw = re.sub(r'[^A-Z0-9]', '', raw.upper())
        if self._validate(raw): return raw # Nếu đã chuẩn, trả về luôn
        
        # Nếu chưa chuẩn, thử dùng hàm Heuristic để "cứu" kết quả
        fixed = self._fix_ocr(raw)
        if self._validate(fixed): return fixed
        return None

    def _get_sharpness(self, img):
        """Thuật toán đánh giá độ nét của ảnh dùng phương sai Laplacian"""
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return cv2.Laplacian(gray, cv2.CV_64F).var()
        except:
            return 0.0

    def _run_easyocr(self, img):
        """Nhận diện biển số Offline bằng mô hình AI EasyOCR"""
        if not self.reader: 
            return "Thieu Thiet Lap"
        try:
            # TỐI ƯU HÓA TỐC ĐỘ: Thu nhỏ kích thước ảnh xuống chiều ngang tối đa 800px
            # Điều này giúp EasyOCR chạy nhanh gấp 3-5 lần mà không suy giảm đáng kể độ chính xác
            h, w = img.shape[:2]
            max_width = 800
            if w > max_width:
                ratio = max_width / float(w)
                new_h = int(h * ratio)
                img_resized = cv2.resize(img, (max_width, new_h), interpolation=cv2.INTER_AREA)
            else:
                img_resized = img

            # Chạy mô hình trích xuất chữ (Allowlist: Giới hạn chỉ nhận diện chữ và số)
            results = self.reader.readtext(img_resized, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', detail=0)
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
        
        p(f"    -> [AI] Bắt đầu chạy Nhận diện trên ảnh nét nhất... (Chế độ: {self.mode})")
        
        for score, frame, orig_idx in scored_frames:
            p(f"      -> Đang phân tích ảnh gốc số {orig_idx} (Độ nét: {score:.1f})...")
            
            res = None
            engine_used = "EasyOCR"
            
            # CHẾ ĐỘ HYBRID: Chạy Gemini trước, nếu rớt mạng thì lập tức Fallback về EasyOCR
            if self.mode == "gemini" and self.api_key:
                p("      -> [AI] Đang gọi Google Gemini API (Cloud)...")
                res = self._run_gemini(frame)
                
                # Nếu Gemini trả về lỗi mạng hoặc lỗi API, kích hoạt cơ chế Fallback
                if res and res not in ("Mat Mang", "Thieu API Key", "Khong Co Gemini", "Loi Phan Mem", "Khong Thay Bien"):
                    engine_used = "Gemini 1.5"
                else:
                    p("      -> [AI] Gemini thất bại (Mất mạng hoặc Lỗi). TỰ ĐỘNG FALLBACK sang EasyOCR Offline!")
                    res = self._run_easyocr(frame)
                    engine_used = "EasyOCR (Fallback)"
            else:
                # Chế độ thuần Offline
                res = self._run_easyocr(frame)
                engine_used = "EasyOCR"
            
            # Đánh giá kết quả
            if res and res not in ("Khong Thay Bien", "Thieu Thiet Lap", "Loi Phan Mem", "Mat Mang", "Thieu API Key"):
                if self._validate(res):
                    p(f"      -> [OK] Tìm thấy biển số chuẩn '{res}' bằng {engine_used}!")
                    return res, engine_used, frame
                else:
                    p(f"      -> [WARN] Nhận diện ra '{res}' nhưng sai định dạng Biển VN.")
                    # Lưu tạm kết quả sai định dạng vào best_overall để dùng nếu các ảnh khác đều xịt
                    if not best_overall:
                        best_overall = res
                        best_frame = frame
            else:
                p(f"      -> [FAIL] Không thể đọc được biển số trên ảnh này.")
                
        # Nếu duyệt qua tất cả ảnh mà không có cái nào chuẩn 100%, trả về kết quả khả dĩ nhất
        return best_overall if best_overall else "Khong Nhan Dien Duoc", "EasyOCR", best_frame
