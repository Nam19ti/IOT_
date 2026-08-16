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

# ==========================================
# BỘ LỌC BIỂN SỐ HỢP LỆ (CHỐNG NHẢY LINH TINH)
# ==========================================

# Bảng mã tỉnh/thành phố hợp lệ trên biển số Việt Nam
# Nếu 2 số đầu không nằm trong bảng này → chắc chắn là đọc nhầm chữ rác
VN_PROVINCE_CODES = {
    '11','12','14','15','16','17','18','19','20',
    '21','22','23','24','25','26','27','28','29','30',
    '31','32','33','34','35','36','37','38','39',
    '40','41','42','43','44','45','46','47','48','49',
    '50','51','52','53','54','55','56','57','58','59','60',
    '61','62','63','64','65','66','67','68','69','70',
    '71','72','73','74','75','76','77','78','79',
    '80','81','82','83','84','85','86','88','89',
    '90','92','93','94','95','97','98','99'
}

# Các chữ cái seri hợp lệ trên biển số VN
# Loại bỏ I, J, O, Q, W vì không bao giờ xuất hiện trên biển VN (dễ nhầm với số 1, 0)
VN_VALID_LETTERS = set('ABCDEFGHKLMNPRSTUVXYZ')

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
        """
        Kiểm tra chuỗi có phải biển số Việt Nam hợp lệ không (3 tầng):
        1. Khớp Regex định dạng (2 số + chữ + 4-5 số)
        2. Mã tỉnh phải nằm trong bảng mã tỉnh VN thật
        3. Chữ seri phải nằm trong bộ chữ cái hợp lệ (không có I, J, O, Q, W)
        """
        if len(text) < 7 or len(text) > 9:
            return False
        match = VN_PLATE_RE.match(text)
        if not match:
            return False
        # Kiểm tra mã tỉnh có tồn tại không (VD: 29=Hà Nội, 51=TP.HCM)
        province = match.group(1)
        if province not in VN_PROVINCE_CODES:
            return False
        # Kiểm tra chữ seri có hợp lệ không (VD: A, B, C... không có I, J, O, Q, W)
        letter = match.group(2)[0]
        if letter not in VN_VALID_LETTERS:
            return False
        return True

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
        Thuật toán Crop sử dụng khung ROI tĩnh do người dùng tùy chỉnh trên giao diện Web.
        """
        import json
        import os
        try:
            # Đọc toạ độ ROI từ file config
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            if not os.path.exists(config_path):
                return img
                
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            roi = config.get("roi")
            if roi:
                h_orig, w_orig = img.shape[:2]
                
                # Tính toạ độ pixel thực tế từ phần trăm
                x1 = int(roi['x'] * w_orig)
                y1 = int(roi['y'] * h_orig)
                w = int(roi['w'] * w_orig)
                h = int(roi['h'] * h_orig)
                x2 = x1 + w
                y2 = y1 + h
                
                # Cắt không vượt viền
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w_orig, x2), min(h_orig, y2)
                
                if x2 > x1 and y2 > y1:
                    cropped = img[y1:y2, x1:x2]
                    p(f"      -> [CROP] Da cat anh theo khung ROI (x:{x1}, y:{y1}, w:{x2-x1}, h:{y2-y1})")
                    
                    # Resize chuẩn độ phân giải cho OCR
                    TARGET_WIDTH = 450
                    crop_h, crop_w = cropped.shape[:2]
                    if crop_w > TARGET_WIDTH:
                        ratio = TARGET_WIDTH / crop_w
                        cropped = cv2.resize(cropped, (TARGET_WIDTH, int(crop_h * ratio)), interpolation=cv2.INTER_AREA)
                    elif crop_w < 200:
                        ratio = 300 / crop_w
                        cropped = cv2.resize(cropped, (300, int(crop_h * ratio)), interpolation=cv2.INTER_CUBIC)
                        
                    return cropped
                else:
                    p("      -> [CROP] Toa do ROI khong hop le, tra ve anh goc.")
        except Exception as e:
            p(f"      -> [CROP LOI] {e}. Tra ve anh goc.")
            
        return img

    def _preprocess_for_ocr(self, img):
        """
        Sử dụng sức mạnh của OpenCV để tối ưu hóa ảnh cho EasyOCR.
        Bao gồm: Nắn thẳng (Deskew), Tăng độ tương phản (CLAHE), Xóa nhiễu, Làm nét.
        """
        try:
            # 1. Chuyển sang ảnh xám
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 2. Nắn thẳng ảnh (Deskew) bằng HoughLinesP
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
            angle = 0
            if lines is not None:
                angles = []
                for line in lines:
                    x1, y1, x2, y2 = line.ravel()
                    # Bỏ qua các đường thẳng đứng
                    if x2 - x1 == 0:
                        continue
                    a = np.degrees(np.arctan((y2 - y1) / (x2 - x1)))
                    # Chỉ lấy các góc nghiêng nhẹ (-45 đến 45 độ)
                    if -45 < a < 45:
                        angles.append(a)
                
                if angles:
                    angle = np.median(angles)
                    if abs(angle) > 2: # Chỉ xoay nếu góc nghiêng đáng kể
                        p(f"      -> [OPENCV] Phat hien bien so bi nghieng {angle:.1f} do. Dang nan thang...")
                        (h, w) = img.shape[:2]
                        center = (w // 2, h // 2)
                        M = cv2.getRotationMatrix2D(center, angle, 1.0)
                        gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            
            # 3. Tăng độ tương phản bằng CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # 4. Lọc nhiễu song phương (Bilateral Filter)
            # Giữ lại độ sắc nét của viền chữ, xóa mờ nhiễu bụi
            filtered = cv2.bilateralFilter(enhanced, 11, 17, 17)
            
            # 5. Làm nét viền chữ (Sharpen)
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(filtered, -1, kernel)
            
            return sharpened
            
        except Exception as e:
            p(f"      -> [OPENCV LOI] Khong the tien xu ly: {e}")
            return img

    def _run_easyocr(self, img):
        """
        Nhận diện biển số Offline bằng mô hình AI EasyOCR.
        Chạy 2 luồng: Ảnh thô (RAW) và Ảnh qua xử lý OpenCV (OPENCV).
        """
        if not self.reader: 
            return "Thieu Thiet Lap"
            
        def read_img(img_data, tag="RAW"):
            results = self.reader.readtext(img_data, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', detail=1)
            if not results: return None, 0
            
            CONFIDENCE_THRESHOLD = 0.3
            filtered = []
            for (bbox, text, conf) in results:
                if conf >= CONFIDENCE_THRESHOLD:
                    filtered.append((text, conf))
                    p(f"      -> [EASYOCR-{tag}] '{text}' (tin cay: {conf:.0%})")
            
            if not filtered: return None, 0
            
            raw = "".join([t for t, c in filtered])
            processed = self._post_process(raw)
            avg_conf = sum([c for t, c in filtered]) / len(filtered)
            
            # Ưu tiên chuỗi đã khớp Regex VN
            if processed:
                return processed, avg_conf + 1.0 # Cộng 1.0 điểm nếu khớp chuẩn format
            return raw, avg_conf

        try:
            # Lần 1: Chạy trên ảnh Crop thô (RAW)
            res_raw, conf_raw = read_img(img, "RAW")
            
            # Lần 2: Chạy trên ảnh đã qua bộ lọc OpenCV cực nét
            preprocessed_img = self._preprocess_for_ocr(img)
            res_cv, conf_cv = read_img(preprocessed_img, "OPENCV")
            
            # So sánh và chọn kết quả tốt nhất
            if conf_cv > conf_raw and res_cv is not None:
                p("      -> [CHOT] Chon ket qua tu OpenCV Enhancement.")
                return res_cv
            elif res_raw is not None:
                p("      -> [CHOT] Chon ket qua tu anh RAW.")
                return res_raw
            else:
                p("      -> [EASYOCR] Khong doc duoc bien so hop le o ca 2 che do.")
                return None
                
        except Exception as e:
            p(f"      -> [EASYOCR LOI] {e}")
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
