import cv2
import urllib.request
import urllib.parse
import numpy as np
import requests
from core import p

class CameraClient:
    """
    Lớp CameraClient (Trình điều khiển Camera qua Mạng LAN)
    Chức năng chính:
    - Bắt luồng ảnh tĩnh (Snapshot) thông qua HTTP GET từ điện thoại Android (App IP Webcam / DroidCam).
    - Tự động chuẩn hóa địa chỉ URL người dùng nhập vào.
    - Ép kiểu dữ liệu luồng byte thành mảng đa chiều NumPy để thư viện OpenCV xử lý được.
    """
    def __init__(self, url):
        self.url = url
        self.set_url(url)

    def set_url(self, new_url):
        """
        Hàm gán và chuẩn hóa URL.
        """
        raw = new_url.strip() if new_url else ""
        if not raw:
            self.url = ""
            return

        # 1. Đảm bảo có giao thức http:// hoặc https:// hoặc rtsp:// TRƯỚC KHI parse URL
        if not (raw.startswith("http://") or raw.startswith("https://") or raw.startswith("rtsp://")):
            raw = "http://" + raw

        # 2. Parse URL sau khi đã có http://
        parsed = urllib.parse.urlparse(raw)
        
        # Nếu người dùng chỉ gõ IP và Port (vd: http://192.168.1.100:8080 hoặc http://192.168.1.100:8080/)
        if not parsed.path or parsed.path == "/":
            self.url = raw.rstrip("/") + "/shot.jpg"
        else:
            self.url = raw

        p(f"[CAMERA] Đã cập nhật URL camera chuẩn: {self.url}")

    def fetch_image(self):
        """
        Lấy 1 khung hình (Frame) duy nhất từ luồng IP Webcam / Camera.
        Tự động thử nghiệm các đường dẫn ảnh tĩnh tương thích (/photo.jpg, /shot.jpg).
        """
        if not self.url:
            p("[CAMERA LỖI] URL Camera đang bị trống!")
            return None

        # Tạo danh sách các URL ứng viên (Thử URL nhập chính xác -> /shot.jpg -> /photo.jpg)
        candidate_urls = [self.url]
        base_url = self.url.rstrip("/")
        
        # Nếu URL chưa có đuôi ảnh cụ thể, bổ sung thêm các endpoint phổ biến
        if not any(self.url.endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
            if not self.url.endswith("/shot.jpg"):
                candidate_urls.append(base_url + "/shot.jpg")
            if not self.url.endswith("/photo.jpg"):
                candidate_urls.append(base_url + "/photo.jpg")

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Connection": "close"
        }

        # Dùng duy nhất urllib với Header nhẹ nhàng để tránh bị Android 11+ chặn, đồng thời không bị overhead như thư viện requests.
        for target_url in candidate_urls:
            try:
                req = urllib.request.Request(target_url, headers=headers)
                # Timeout 5s để đảm bảo không bị sập, nhưng do có header chuẩn nên sẽ phản hồi ngay lập tức (~0.1s)
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    arr = np.asarray(bytearray(resp.read()), dtype=np.uint8)
                    img = cv2.imdecode(arr, -1)
                    
                    if img is not None and img.size > 0:
                        if target_url != self.url:
                            self.url = target_url
                        return img
            except Exception as e:
                p(f"[CAMERA LỖI KẾT NỐI] {target_url}: {e}")

        # Fallback bằng OpenCV VideoCapture nếu là luồng stream video (rtsp/mjpg)
        if "rtsp://" in self.url or ".mjpg" in self.url or ".mp4" in self.url:
            try:
                cap = cv2.VideoCapture(self.url)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None and frame.size > 0:
                    return frame
            except Exception as e_stream:
                p(f"[CAMERA LỖI STREAM]: {e_stream}")

        return None

    def get_data(self):
        """
        (Hàm Legacy / Giữ lại cho tương thích ngược)
        Trả về nguyên khung hình (Full Frame).
        """
        frame = self.fetch_image()
        return frame, None

    def capture_frames(self, num_frames=1, interval=0):
        """
        Chụp một mảng các khung hình.
        Tuy nhiên trong phiên bản Zero-Crash này, ta chỉ cần chụp chính xác 1 bức ảnh sắc nét nhất 
        để tiết kiệm tài nguyên CPU.
        """
        frame = self.fetch_image()
        if frame is not None and frame.size > 0:
            return [(frame, None)]
        return []

