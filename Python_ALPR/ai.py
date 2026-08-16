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

    def _order_points(self, pts):
        """
        Sắp xếp 4 điểm theo thứ tự chuẩn: Trái-Trên, Phải-Trên, Phải-Dưới, Trái-Dưới.
        Dùng cho Perspective Transform - đảm bảo 4 góc nguồn khớp đúng 4 góc đích.
        Thuật toán: Dùng tổng (x+y) để tìm TL (nhỏ nhất) và BR (lớn nhất),
                    dùng hiệu (x-y) để tìm TR (nhỏ nhất) và BL (lớn nhất).
        """
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]   # Trái-Trên: x+y nhỏ nhất
        rect[2] = pts[np.argmax(s)]   # Phải-Dưới: x+y lớn nhất
        d = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(d)]   # Phải-Trên: y nhỏ, x lớn → x-y nhỏ nhất
        rect[3] = pts[np.argmax(d)]   # Trái-Dưới: y lớn, x nhỏ → x-y lớn nhất
        return rect

    def _crop_plate(self, img):
        """
        Thuat toan Crop v3: Edge Detection — Khong phu thuoc mau sac.
        Hoat dong voi moi mau xe (trang, den, do...) va moi loai bien (trang, vang, xanh).
        
        Buoc 1: Thu nho anh 18% de xu ly nhanh
        Buoc 2: Bilateral Filter giu canh sac + Canny Edge Detection
        Buoc 3: Morphology Close + Dilate noi cac canh ky tu thanh 1 khoi
        Buoc 4: Loc contour theo 4 tieu chi:
                 - Dien tich (0.5% ~ 15% tong anh)
                 - Ty le canh (0.8 ~ 6.0)
                 - Do chu nhat / Solidity (> 0.35)
                 - Phuong sai Grayscale (> 800 = co chu ben trong)
                 + Bonus cho hinh tu giac (approxPolyDP = 4 dinh)
        Buoc 5: minAreaRect + boxPoints → Scale len anh goc
        Buoc 6: Perspective Transform nan thang bien nghieng
        Buoc 7: Resize ve ~450px cho OCR
        """
        try:
            h_orig, w_orig = img.shape[:2]
            SCALE_FACTOR = 0.18  # Thu nho xuong 18% kich thuoc goc

            # ============================================
            # BUOC 1: Thu nho anh de xu ly nhanh
            # ============================================
            small_w = int(w_orig * SCALE_FACTOR)
            small_h = int(h_orig * SCALE_FACTOR)
            if small_w < 10 or small_h < 10:
                p("      -> [CROP] Anh qua nho, bo qua crop.")
                return img
            small = cv2.resize(img, (small_w, small_h), interpolation=cv2.INTER_AREA)
            p(f"      -> [CROP] Thu nho 18%: {w_orig}x{h_orig} -> {small_w}x{small_h}")

            # ============================================
            # BUOC 2: Edge Detection (KHONG phu thuoc mau sac)
            # ============================================
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            # Bilateral Filter: Lam min nhieu nhung GIU NGUYEN canh sac net
            # Rat tot cho bien so vi ky tu co canh sac, nen thi min
            blurred = cv2.bilateralFilter(gray, 11, 17, 17)
            # Canny Edge: Phat hien moi canh trong anh, bat ke mau sac
            edges = cv2.Canny(blurred, 30, 200)

            # ============================================
            # BUOC 3: Morphology — Noi cac canh ky tu thanh 1 khoi
            # ============================================
            # Kernel ngang dai hon doc vi bien so ngang > doc
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3))
            # Close: Lap day khoang trong giua cac ky tu
            closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
            # Dilate: Mo rong them de dam bao cac ky tu dinh lien nhau
            closed = cv2.dilate(closed, kernel, iterations=1)

            # ============================================
            # BUOC 4: Tim contours va loc thong minh
            # ============================================
            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                p("      -> [CROP] Khong tim thay contour nao. Tra anh goc.")
                return img

            total_area = small_w * small_h
            candidates = []

            for c in contours:
                area = cv2.contourArea(c)

                # --- LOC 1: Dien tich (0.5% ~ 15% tong anh) ---
                # Bien so thuong chiem 0.5-15% dien tich anh chup
                # Nhieu nho (oc vit, den) < 0.5% → loai
                # Vung qua lon (than xe, bau troi) > 15% → loai
                area_ratio = area / total_area
                if area_ratio < 0.005 or area_ratio > 0.15:
                    continue

                # --- LOC 2: Ty le canh (Aspect Ratio) ---
                rect = cv2.minAreaRect(c)
                (cx, cy), (rw, rh), angle = rect
                if rw == 0 or rh == 0:
                    continue
                # Dam bao rw luon la canh dai hon
                if rw < rh:
                    rw, rh = rh, rw
                aspect = rw / rh
                # Bien ngang VN: ty le ~2.0 ~ 5.0
                # Bien vuong VN (2 dong): ty le ~0.8 ~ 1.5
                # Gop chung: 0.8 ~ 6.0
                if aspect < 0.8 or aspect > 6.0:
                    continue

                # --- LOC 3: Do chu nhat (Rectangularity / Solidity) ---
                # Bien so la hinh chu nhat → contour_area / rect_area cao (> 0.35)
                # Hinh dang bat ky (canh cua, guong xe) → solidity thap
                rect_area = rw * rh
                solidity = area / rect_area if rect_area > 0 else 0
                if solidity < 0.35:
                    continue

                # --- LOC 4: Phuong sai Grayscale (Co chu ben trong?) ---
                # Bien so co ky tu → do tuong phan cao → phuong sai lon (> 800)
                # Vung tron tru (than xe, mat duong) → phuong sai thap
                x_b, y_b, w_b, h_b = cv2.boundingRect(c)
                roi = gray[y_b:y_b+h_b, x_b:x_b+w_b]
                if roi.size == 0:
                    continue
                variance = float(np.var(roi))
                if variance < 800:
                    continue

                # Tinh diem cho ung vien
                # approxPolyDP: Neu contour xap xi thanh tu giac (4 dinh) → rat co kha nang la bien so
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.04 * peri, True)

                score = solidity * 0.4 + min(variance / 5000, 1.0) * 0.3 + area_ratio * 0.1
                if len(approx) == 4:
                    score += 0.3  # Bonus lon cho hinh 4 canh (chu nhat)
                elif len(approx) >= 4 and len(approx) <= 6:
                    score += 0.1  # Bonus nho cho hinh gan chu nhat

                p(f"      -> [CROP] Ung vien: area={area_ratio:.1%}, aspect={aspect:.1f}, solid={solidity:.2f}, var={variance:.0f}, vert={len(approx)}, score={score:.3f}")
                candidates.append((score, c, rect))

            if not candidates:
                p("      -> [CROP] Khong co ung vien nao qua bo loc. Tra anh goc.")
                return img

            # Chon ung vien tot nhat (score cao nhat)
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_contour, best_rect = candidates[0]
            p(f"      -> [CROP] Chon ung vien tot nhat (score={best_score:.3f})")

            # ============================================
            # BUOC 5: Lay 4 goc + Scale len anh goc
            # ============================================
            box_small = cv2.boxPoints(best_rect)
            scale_up = 1.0 / SCALE_FACTOR  # ~ 5.56
            box_orig = box_small * scale_up
            # Clamp toa do vao gioi han anh goc
            box_orig[:, 0] = np.clip(box_orig[:, 0], 0, w_orig - 1)
            box_orig[:, 1] = np.clip(box_orig[:, 1], 0, h_orig - 1)

            # ============================================
            # BUOC 6: Perspective Transform - Nan thang bien nghieng
            # ============================================
            ordered = self._order_points(box_orig)
            (tl, tr, br, bl) = ordered

            # Tinh kich thuoc hinh chu nhat dich
            width_top = np.linalg.norm(tr - tl)
            width_bot = np.linalg.norm(br - bl)
            dst_w = int(max(width_top, width_bot))

            height_left = np.linalg.norm(bl - tl)
            height_right = np.linalg.norm(br - tr)
            dst_h = int(max(height_left, height_right))

            if dst_w < 10 or dst_h < 10:
                p("      -> [CROP] Vung crop qua nho sau scale. Tra anh goc.")
                return img

            # Padding 10% moi chieu de khong cat sat mep bien so
            pad_x = int(dst_w * 0.10)
            pad_y = int(dst_h * 0.10)

            src_padded = np.array([
                [max(0, tl[0] - pad_x), max(0, tl[1] - pad_y)],
                [min(w_orig - 1, tr[0] + pad_x), max(0, tr[1] - pad_y)],
                [min(w_orig - 1, br[0] + pad_x), min(h_orig - 1, br[1] + pad_y)],
                [max(0, bl[0] - pad_x), min(h_orig - 1, bl[1] + pad_y)]
            ], dtype="float32")

            dst_w_padded = dst_w + 2 * pad_x
            dst_h_padded = dst_h + 2 * pad_y

            dst = np.array([
                [0, 0],
                [dst_w_padded - 1, 0],
                [dst_w_padded - 1, dst_h_padded - 1],
                [0, dst_h_padded - 1]
            ], dtype="float32")

            M = cv2.getPerspectiveTransform(src_padded, dst)
            warped = cv2.warpPerspective(img, M, (dst_w_padded, dst_h_padded))

            # ============================================
            # BUOC 7: Resize ve do phan giai vua phai cho OCR
            # ============================================
            TARGET_WIDTH = 450
            warp_h, warp_w = warped.shape[:2]
            if warp_w > TARGET_WIDTH:
                ratio = TARGET_WIDTH / warp_w
                warped = cv2.resize(warped, (TARGET_WIDTH, int(warp_h * ratio)), interpolation=cv2.INTER_AREA)
            elif warp_w < 200:
                ratio = 300 / warp_w
                warped = cv2.resize(warped, (300, int(warp_h * ratio)), interpolation=cv2.INTER_CUBIC)

            p(f"      -> [CROP] Deskew thanh cong! Kich thuoc cuoi: {warped.shape[1]}x{warped.shape[0]}")
            return warped

        except Exception as e:
            p(f"      -> [CROP LOI] {e}")
            return img  # Fallback: tra anh goc neu loi

    def _run_easyocr(self, img):
        """
        Nhận diện biển số Offline bằng mô hình AI EasyOCR.
        Dùng detail=1 để lấy độ tin cậy (confidence) → lọc bỏ chữ rác có confidence thấp.
        """
        if not self.reader: 
            return "Thieu Thiet Lap"
        try:
            # detail=1 trả về (bbox, text, confidence) thay vì chỉ text
            # Giúp lọc được các đoạn chữ rác mà EasyOCR đọc nhầm từ nền ảnh
            results = self.reader.readtext(img, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', detail=1)
            if not results:
                return None
            
            # Ngưỡng tin cậy tối thiểu 30% - dưới mức này là chữ rác/nhiễu
            CONFIDENCE_THRESHOLD = 0.3
            filtered = []
            for (bbox, text, conf) in results:
                if conf >= CONFIDENCE_THRESHOLD:
                    filtered.append((text, conf))
                    p(f"      -> [EASYOCR] '{text}' (tin cay: {conf:.0%})")
                else:
                    p(f"      -> [EASYOCR] Bo qua '{text}' (tin cay qua thap: {conf:.0%})")
            
            if not filtered:
                p("      -> [EASYOCR] Tat ca ky tu deu duoi nguong tin cay 30%. Bo qua.")
                return None
            
            # Nối các dòng chữ đạt chuẩn lại với nhau (xử lý biển vuông 2 dòng)
            raw = "".join([t for t, c in filtered])
            processed = self._post_process(raw)
            return processed if processed else raw
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
